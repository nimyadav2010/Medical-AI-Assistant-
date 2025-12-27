import os
from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool

from tools.appointment_tool import AppointmentAdapter
from tools.ehr_tool import EHRAdapter
from tools.search_tool import SearchTool
from tools.rag_tool import RAGTool
from tools.email_tool import EmailTool
import httpx

# Initialize Tools
appt_tool = AppointmentAdapter()
ehr_tool = EHRAdapter()
search_tool = SearchTool()
rag_tool = RAGTool(db_path="./chroma_db")
email_tool = EmailTool()

# Define State
class AgentState(TypedDict):
    messages: List[BaseMessage]
    patient_name: str
    current_plan: List[str]
    results: dict

# LLM
# Using gpt-3.5-turbo as it is more commonly available
# Disable SSL verification for OpenAI API calls due to network restrictions
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, http_client=httpx.Client(verify=False))

# Nodes
def planner_node(state: AgentState):
    messages = state['messages']
    last_message = messages[-1].content.strip()
    current_patient = state.get('patient_name', 'None')
    
    updates = {}

    # Heuristic: If single word and looks like a name, force switch
    # This bypasses LLM uncertainty for simple name switches
    # Exclude common commands/greetings
    ignored_words = ["help", "stop", "exit", "quit", "hello", "hi", "hey", "menu", "start", "restart"]
    
    # 1. Single word check
    if " " not in last_message and len(last_message) > 2 and last_message.lower() not in ignored_words:
         updates['patient_name'] = last_message
         updates['current_plan'] = ["get_patient_history", "query_medical_docs"]
         return updates

    # 2. Two words check (e.g. "Vimla patient", "patient Vimla")
    words = last_message.split()
    if len(words) == 2:
        if words[1].lower() == "patient" and words[0].lower() not in ignored_words:
             updates['patient_name'] = words[0]
             updates['current_plan'] = ["get_patient_history", "query_medical_docs"]
             return updates
        elif words[0].lower() == "patient" and words[1].lower() not in ignored_words:
             updates['patient_name'] = words[1]
             updates['current_plan'] = ["get_patient_history", "query_medical_docs"]
             return updates
    
    prompt = ChatPromptTemplate.from_template(
        """You are a healthcare assistant planner.
        Current Patient Context: {current_patient}
        User Request: {request}
        
        First, check if the user is mentioning a specific patient name (e.g., "Show me Nirmala", "Deepak", "Book for John", "Vimla", "pull document for Vimla").
        Look for names that might be capitalized or appear as the subject of the request.
        
        If a NEW patient name is found (different from Current Patient Context), start your response with "PATIENT: [Name]" on the first line.
        Example:
        Request: "can u pull the document for Vimla patient" -> Output: "PATIENT: Vimla"
        
        Next, evaluate if the request is related to healthcare, medical issues, patient data, appointments, or system capabilities.
        If the request is just a name (e.g. "Nirmala", "Vimla"), treat it as a request to "get_patient_history" and "query_medical_docs" for that patient.
        
        If the request is NOT related (e.g., "dance", "singing", "weather", "joke", "hello"), return exactly: "N/A"
        
        If it IS related, break down this request into a sequential plan of steps.
        Available tools:
        - get_patient_history: Get medical history for a patient.
        - book_appointment: Book an appointment with a doctor.
        - search_medical_info: Search for general medical info.
        - query_medical_docs: Query internal medical documents (RAG).
        - bulk_email_campaign: Find patients with specific conditions and send emails.
        
        Return the plan as a numbered list.
        """
    )
    chain = prompt | llm | StrOutputParser()
    response_text = chain.invoke({"request": last_message, "current_patient": current_patient})
    
    lines = response_text.strip().split('\n')
    
    # Check for PATIENT: override
    if lines and lines[0].startswith("PATIENT:"):
        new_name = lines[0].replace("PATIENT:", "").strip()
        # Only update if it's a valid string
        if new_name and new_name.lower() != "none":
            updates['patient_name'] = new_name
        # Remove the PATIENT line from the plan
        plan_lines = lines[1:]
    else:
        plan_lines = lines
        
    # Clean up empty lines
    plan_lines = [l for l in plan_lines if l.strip()]
    
    updates['current_plan'] = plan_lines
    return updates

def executor_node(state: AgentState):
    plan = state['current_plan']
    
    # Check if plan is N/A
    if plan and "N/A" in plan[0]:
        return {"messages": [AIMessage(content="N/A")], "results": {}}

    patient_name = state.get('patient_name')
    messages = state['messages']
    last_message = messages[-1].content
    
    results = {}
    plan_str = " ".join(plan).lower()
    
    # 1. Execute Tools based on the Plan
    
    # ALWAYS fetch patient details if name is available, to populate the summary section
    if patient_name:
        # Try to get structured data first
        patient_details = ehr_tool.get_patient_summary(patient_name)
        if patient_details:
            results['patient_details'] = patient_details
        else:
            # If not in EHR, try to find in RAG
            rag_summary = rag_tool.query(f"Summary of patient {patient_name}")
            if rag_summary:
                # Verify that the retrieved summary actually mentions the patient name
                # This prevents returning "Neerav" when searching for "Vimla"
                if patient_name.lower() in rag_summary[0].lower():
                    results['patient_details'] = {"Summary": rag_summary[0], "Source": "RAG"}
                else:
                    results['patient_details'] = "Patient details not found (RAG mismatch)."
            else:
                results['patient_details'] = "Patient details not found."
        
        # Also fetch general medical context from RAG for this patient (for the report)
        rag_context = rag_tool.query(f"Medical history and conditions of {patient_name}")
        
        # Filter RAG context to ensure it mentions the patient name
        # This prevents false positives where RAG returns a document for another patient
        filtered_context = []
        if rag_context:
            for doc_content in rag_context:
                if patient_name.lower() in doc_content.lower():
                    filtered_context.append(doc_content)
        
        results['patient_rag_context'] = filtered_context

    # Step A: Retrieve History (Explicit request)
    if "history" in plan_str or "record" in plan_str:
        if patient_name:
            hist = ehr_tool.get_patient_history(patient_name)
            results['history'] = hist
        else:
            results['history'] = "Patient name missing."

    # Step B: RAG Search / Treatment Options
    # Always try to query RAG with the user's message if it looks like a question, 
    # or if we haven't found context yet.
    if "search" in plan_str or "treatment" in plan_str or "rag" in plan_str or "summarize" in plan_str or "?" in last_message:
        # Use the user's message as the query
        rag_results = rag_tool.query(last_message)
        results['rag_results'] = rag_results

    # Step C: Book Appointment (Auto-Booking Logic)
    if "book" in plan_str or "appointment" in plan_str:
        # 1. Check Availability
        # For demo, we assume Nephrologist if mentioned, else General
        doc_id = "dr_nephrologist" if "nephrologist" in last_message.lower() else "dr_gp"
        avail = appt_tool.get_availability(doc_id)
        results['availability'] = avail
        
        # 2. Auto-Book if slots are available
        if avail:
            # Pick the first slot automatically
            selected_slot = avail[0]
            
            # Get patient email if available
            patient_email = None
            if 'patient_details' in results and isinstance(results['patient_details'], dict):
                # Check both 'Email' and 'email' keys
                patient_email = results['patient_details'].get('Email') or results['patient_details'].get('email')

            booking = appt_tool.book_appointment(
                patient_id=patient_name,
                time=selected_slot['start'],
                doctor_id=doc_id,
                reason="Auto-booked by AI Assistant",
                patient_email=patient_email
            )
            results['booking_status'] = booking
        else:
            results['booking_status'] = {"success": False, "error": "No slots available"}

    # Step D: Bulk Email Campaign
    if "email" in plan_str and ("all" in plan_str or "patients" in plan_str or "campaign" in plan_str or "bulk" in plan_str):
        # Extract condition from message (simple heuristic)
        condition = "unknown"
        if "cancer" in last_message.lower():
            condition = "cancer"
        elif "diabetic" in last_message.lower() or "diabetes" in last_message.lower():
            condition = "diabet" # partial match
        elif "allergy" in last_message.lower() or "allergies" in last_message.lower():
            condition = "allerg"
            
        if condition != "unknown":
            target_patients = ehr_tool.search_patients(condition)
            results['target_patients'] = [p.get('Name') for p in target_patients]
            
            email_results = []
            for p in target_patients:
                email = p.get('Email')
                name = p.get('Name')
                if email:
                    subject = f"Important Health Check-up: {condition.capitalize()} Screening"
                    body = f"""
                    Dear {name},
                    
                    Based on your medical profile, we recommend a check-up regarding {condition}.
                    Please contact us to schedule an appointment.
                    
                    Best regards,
                    AI Medical Assistant
                    """
                    res = email_tool.send_email(email, subject, body)
                    email_results.append(f"{name}: {res.get('message') or res.get('error')}")
                else:
                    email_results.append(f"{name}: No email found.")
            results['campaign_results'] = email_results
        else:
            results['campaign_results'] = "Could not identify a specific condition (cancer, diabetes, allergy) to filter patients."

    # Explicitly flag if any email action was taken to prevent hallucinations
    email_action_taken = False
    if "campaign_results" in results:
        email_action_taken = True
    if "booking_status" in results and "email" in str(results["booking_status"]).lower():
        email_action_taken = True
    
    results["_meta_email_action_taken"] = email_action_taken

    # 2. Generate Natural Language Response
    system_prompt = f"""You are a smart Agentic Healthcare Assistant.
    
    User Request: "{last_message}"
    Patient: {patient_name}
    
    You have executed the following plan:
    {plan}
    
    Here are the results from your tools:
    {results}
    
    Task:
    First, determine if the User Request is related to healthcare, patient management, appointments, or medical information.
    
    If the request is NOT related (e.g., "dance", "weather", "sports", "joke"), simply respond with:
    "N/A"
    
    If the request IS related, generate a structured response using the following numbered format:
    
    1. **Patient Summary**: [Name], [Age], [Gender]. [Brief Summary]
    2. **RAG Search Results / Treatment Options**: [Key findings from RAG. If specific search results are empty, summarize the patient's medical history from 'patient_rag_context' if available.]
    3. **Appointment Status**: [Booking Details including Doctor, Time, and Status. If no appointment was booked or queried in this session, MUST state "N/A"]
    4. **Email Notification Status**:
       (CRITICAL: Check '_meta_email_action_taken' in results.)
       - If '_meta_email_action_taken' is False: Write "N/A".
       - If '_meta_email_action_taken' is True: List the status. If the tool result says "Email not sent (no recipient provided)", output: "[Patient Name]: Not Sent (No email address provided)".
    
    If a section is not applicable (e.g., no booking made), state "N/A".
    Keep the tone professional and concise.
    """
    
    response = llm.invoke([HumanMessage(content=system_prompt)])
    
    return {"messages": [response], "results": results}

# Graph Construction
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "executor")
workflow.add_edge("executor", END)

app = workflow.compile()
