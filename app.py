import streamlit as st
import os
import sys

# Fix for ChromaDB on Streamlit Cloud (requires sqlite3 >= 3.35.0)
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import httpx
import pandas as pd
import json
import glob
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from agents.agent_graph import app as agent_app
from tools.ehr_tool import EHRAdapter
from tools.appointment_tool import AppointmentAdapter
from tools.rag_tool import RAGTool

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Agentic Healthcare Assistant", layout="wide")

st.title("🏥 Agentic Healthcare Assistant (Live)")

# Initialize Tools
ehr = EHRAdapter()
appt_tool = AppointmentAdapter()
rag = RAGTool(db_path="./chroma_db")

# --- Sidebar: System Status ---
with st.sidebar.expander("🔧 System Status", expanded=True):
    doc_count = rag.get_doc_count()
    st.metric("Knowledge Base Docs", doc_count)
    
    if st.button("Re-build Knowledge Base"):
        with st.spinner("Clearing and Re-ingesting..."):
            rag.clear_db()
            pdf_files = glob.glob(os.path.join("data", "*.pdf"))
            if pdf_files:
                for pdf_path in pdf_files:
                    rag.ingest_pdf(pdf_path)
                st.success(f"Re-ingested {len(pdf_files)} files.")
                st.rerun()
            else:
                st.error("No PDF files found in data/ folder.")

# Auto-Ingest Data on Startup if DB is empty (for Cloud Deployment)
if doc_count == 0:
    with st.spinner("Initializing Knowledge Base... This may take a minute."):
        pdf_files = glob.glob(os.path.join("data", "*.pdf"))
        if pdf_files:
            for pdf_path in pdf_files:
                rag.ingest_pdf(pdf_path)
            st.success(f"Ingested {len(pdf_files)} documents into Knowledge Base.")
            st.rerun()
            st.rerun()

# Initialize Helper LLM for Formatting
# On Windows (Local), we disable SSL verify. On Linux (Cloud), we use default.
if os.name == 'nt':
    _http_client = httpx.Client(verify=False)
else:
    _http_client = None

formatter_llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, http_client=_http_client)

# --- Sidebar: Manage Data ---
with st.sidebar.expander("⚙️ Manage Patients"):
    action = st.radio("Action", ["Add Patient", "Delete Patient"])
    
    if action == "Add Patient":
        with st.form("add_patient_form"):
            new_name = st.text_input("Name")
            new_age = st.number_input("Age", min_value=0, max_value=120)
            new_gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            new_phone = st.text_input("Phone")
            new_email = st.text_input("Email") # Added Email Field
            new_summary = st.text_area("Medical Summary")
            
            uploaded_file = st.file_uploader("Upload Report (PDF) or Data (JSON/Excel)", type=['pdf', 'json', 'xlsx'])
            
            submit_add = st.form_submit_button("Add Patient")
            
            if submit_add:
                # 1. Add Structured Data
                patient_data = {
                    "Name": new_name,
                    "Age": new_age,
                    "Gender": new_gender,
                    "Phone_number": new_phone,
                    "Email": new_email, # Store Email
                    "Summary": new_summary
                }
                
                # Handle File Upload
                if uploaded_file:
                    file_ext = uploaded_file.name.split('.')[-1].lower()
                    save_path = os.path.join("data", uploaded_file.name)
                    
                    # Save file
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    if file_ext == 'pdf':
                        st.info("Ingesting PDF into RAG system...")
                        rag.ingest_pdf(save_path)
                    elif file_ext == 'json':
                        data = json.load(uploaded_file)
                        # Assuming JSON is a single patient dict or list
                        if isinstance(data, dict):
                            ehr.add_patient(data)
                        elif isinstance(data, list):
                            for p in data:
                                ehr.add_patient(p)
                    elif file_ext == 'xlsx':
                        df = pd.read_excel(uploaded_file)
                        for _, row in df.iterrows():
                            ehr.add_patient(row.to_dict())
                
                # Add the manual form data (if name provided)
                if new_name:
                    result = ehr.add_patient(patient_data)
                    if result.get('success'):
                        st.success(f"Patient {new_name} added successfully!")
                        if result.get('warning'):
                            st.warning(result.get('warning'))
                        st.rerun()
                    else:
                        st.error(f"Failed to add patient: {result.get('error')}")
                elif uploaded_file and file_ext == 'pdf':
                     # If PDF uploaded but no name, try to infer or just warn
                     st.warning("PDF ingested, but Patient Record not created because 'Name' was missing. Please add the patient details manually.")

    elif action == "Delete Patient":
        all_patients = ehr.get_all_patient_names()
        patient_to_delete = st.selectbox("Select Patient to Delete", all_patients)
        if st.button("Delete Patient"):
            if ehr.delete_patient(patient_to_delete):
                st.success(f"Deleted {patient_to_delete}")
                st.rerun()
            else:
                st.error("Failed to delete.")

# Sidebar: Patient Context
st.sidebar.header("Patient Context")
# Dynamic patient selection
patient_names = ehr.get_all_patient_names()
if not patient_names:
    patient_names = ["No Patients Found"]
    
selected_patient = st.sidebar.selectbox("Select Patient", patient_names)

if selected_patient and selected_patient != "No Patients Found":
    patient_info = ehr.get_patient_summary(selected_patient)
    if patient_info:
        st.sidebar.subheader("Patient Details")
        st.sidebar.write(f"**Name:** {patient_info.get('Name')}")
        st.sidebar.write(f"**Age:** {patient_info.get('Age')}")
        st.sidebar.write(f"**Gender:** {patient_info.get('Gender')}")
        if patient_info.get('Email'):
            st.sidebar.write(f"**Email:** {patient_info.get('Email')}")
        st.sidebar.write(f"**Summary:** {patient_info.get('Summary')}")
    else:
        st.sidebar.warning("Patient details not found in records.")

# Navigation
# Custom CSS to make the navigation purple and larger
st.markdown("""
    <style>
    /* --- Navigation Radio Buttons --- */
    /* Target the radio button container */
    .stRadio > div {
        background-color: #87CEEB; /* Sky Blue */
        padding: 10px;
        border-radius: 10px;
    }
    
    /* Target the labels (text) */
    .stRadio label p {
        font-size: 20px !important;
        font-weight: 600 !important;
        color: #6A0DAD !important; /* Force Purple Text */
    }
    
    /* Radio Circle (Unchecked) */
    div[role="radiogroup"] label > div:first-of-type {
        border-color: #6A0DAD !important;
        background-color: white !important;
        border-width: 2px !important;
    }
    
    /* Radio Circle (Checked) */
    div[role="radiogroup"] label:has(input:checked) > div:first-of-type {
        border-color: #FF0000 !important;
        background-color: white !important;
    }
    
    /* Inner Radio Circle (Checked) */
    div[role="radiogroup"] label:has(input:checked) > div:first-of-type > div {
        background-color: #FF0000 !important;
    }

    /* Selected Text */
    div[role="radiogroup"] label:has(input:checked) p {
        color: #6A0DAD !important;
        font-weight: 600 !important;
    }
    
    /* Hover effect */
    .stRadio label:hover p {
        color: #2E0854 !important; /* Darker on hover */
    }

    /* --- Headers & Titles --- */
    /* Main Title (h1) */
    h1 {
        color: #8A2BE2 !important; /* Bright BlueViolet */
    }
    
    /* Subheaders (h2, h3) */
    h2, h3 {
        color: #8A2BE2 !important;
    }
    
    /* Sidebar Headers */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3 {
        color: #00BFFF !important; /* Deep Sky Blue */
    }

    /* Expander Header (Manage Data) - Sidebar Only */
    /* Target the summary element (the clickable header) of the expander in the sidebar */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        color: #00BFFF !important; /* Deep Sky Blue */
    }

    /* Target any text elements inside that summary (p, span, div) */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary span,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary div {
        color: #00BFFF !important; /* Deep Sky Blue */
        font-size: 22px !important;
        font-weight: 700 !important;
    }

    /* Target the SVG icon (arrow) */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
        fill: #00BFFF !important;
        color: #00BFFF !important;
    }
    
    /* Expander Content (Inside Manage Data) */
    section[data-testid="stSidebar"] .streamlit-expanderContent {
        background-color: #F0F8FF !important; /* AliceBlue */
        border-left: 1px solid #00BFFF !important;
        border-right: 1px solid #00BFFF !important;
        border-bottom: 1px solid #00BFFF !important;
        border-radius: 0 0 5px 5px !important;
    }
    
    /* Specific Labels in Sidebar (like "Action", "Select Patient") */
    .stSidebar label p {
        color: #8A2BE2 !important;
        font-weight: 500 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Use horizontal radio buttons at the top to simulate a top menu
st.markdown("---")
page = st.radio("Navigate to:", ["🤖 AI Medical Assistant", "📋 Patient Dashboard", "📅 Appointments", "🔬 Query Lab Reports"], horizontal=True)
st.markdown("---")

# --- Page 1: AI Medical Assistant ---
if page == "🤖 AI Medical Assistant":
    st.subheader("AI Medical Assistant")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("How can I help you today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Initialize session state for patient context if not present
                if "agent_patient_context" not in st.session_state:
                    st.session_state.agent_patient_context = selected_patient

                # If the user manually changed the sidebar selection, update the context
                # We can detect this if selected_patient is different from what we stored last time
                # But for now, let's prioritize the agent's internal context if it has drifted, 
                # UNLESS the user explicitly selected someone new in the sidebar.
                # A simple approach: Use the sidebar selection as the base, but if the agent switched it recently, use that?
                # Actually, the simplest fix for the "Vimla" issue is to let the agent's output update the context for the NEXT turn.
                
                # Use the persisted context
                current_context_patient = st.session_state.agent_patient_context
                
                # However, if the user JUST changed the sidebar, we should probably respect that.
                # But Streamlit reruns on change. 
                # Let's assume: 
                # 1. If sidebar matches session_state, use session_state (which might be updated by agent).
                # 2. If sidebar is different, user manually switched, so use sidebar.
                
                if selected_patient != st.session_state.get("last_sidebar_selection", selected_patient):
                     current_context_patient = selected_patient
                     st.session_state.agent_patient_context = selected_patient
                
                st.session_state.last_sidebar_selection = selected_patient

                initial_state = {
                    "messages": [HumanMessage(content=prompt)],
                    "patient_name": current_context_patient,
                    "current_plan": [],
                    "results": {}
                }
                
                try:
                    result = agent_app.invoke(initial_state)
                    
                    # Update the context for the next turn based on what the agent decided
                    new_patient = result.get("patient_name")
                    if new_patient:
                        st.session_state.agent_patient_context = new_patient
                        
                    response_message = result["messages"][-1].content
                    
                    st.markdown(response_message)
                    st.session_state.messages.append({"role": "assistant", "content": response_message})
                    
                    # Display Plan and Debug Info
                    with st.expander("Agent Plan & Execution Details"):
                        st.write("**Plan:**")
                        st.write(result.get("current_plan"))
                        st.write("**Tool Results:**")
                        st.json(result.get("results"))
                        st.write(f"**Patient Context:** {new_patient}")
                        
                except Exception as e:
                    st.error(f"An error occurred: {e}")

# --- Page 2: Patient Dashboard ---
elif page == "📋 Patient Dashboard":
    st.subheader("Patient Dashboard")
    if selected_patient:
        st.info(f"Viewing records for: **{selected_patient}**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Demographics")
            if patient_info:
                st.json(patient_info)
            else:
                st.warning("No demographic data found.")
                
        with col2:
            st.markdown("### Medical History (from RAG)")
            if st.button("Fetch Medical History"):
                with st.spinner("Retrieving and structuring history..."):
                    # 1. Get raw chunks
                    # Use a broader query to ensure we catch the document
                    raw_history = rag.query(f"Medical history and conditions of {selected_patient}")
                    
                    # 2. Format with LLM
                    if isinstance(raw_history, list) and raw_history:
                        # Filter to ensure patient name is in the content (Double Check)
                        filtered_history = [doc for doc in raw_history if selected_patient.lower() in doc.lower()]
                        
                        if filtered_history:
                            context = "\n---\n".join(filtered_history)
                            prompt = f"""
                            You are a medical assistant. Analyze the following patient history snippets and extract key events into a structured Markdown table.
                            
                            Columns: Date, Category (e.g., Diagnosis, Vitals, Procedure), Details.
                            
                            Snippets:
                            {context}
                            """
                            try:
                                response = formatter_llm.invoke(prompt)
                                formatted_history = response.content
                                
                                st.success("History Retrieved")
                                st.markdown(formatted_history)
                                with st.expander("View Raw Source"):
                                    st.write(filtered_history)
                            except Exception as e:
                                st.error(f"Error formatting history: {e}")
                                st.write(filtered_history)
                        else:
                             st.warning(f"No history found for {selected_patient} (Name mismatch in documents).")
                             with st.expander("Debug: Raw Results (Filtered Out)"):
                                 st.write(raw_history)
                    else:
                        st.warning("No history found or error occurred.")
                        with st.expander("Debug: Empty Result"):
                            st.write(f"Query: Medical history and conditions of {selected_patient}")
                            st.write(f"Result: {raw_history}")

# --- Page 3: Appointments ---
elif page == "📅 Appointments":
    st.subheader("Book an Appointment")
    
    with st.form("appointment_form"):
        st.write(f"Booking for: **{selected_patient}**")
        doctor = st.selectbox("Select Doctor", ["Dr. Smith (Cardiology)", "Dr. Jones (General)", "Dr. Lee (Neurology)"])
        date = st.date_input("Date")
        time = st.time_input("Time")
        reason = st.text_area("Reason for Visit")
        
        submitted = st.form_submit_button("Book Appointment")
        
        if submitted:
            # Format date/time for the tool
            datetime_str = f"{date} at {time}"
            # Extract doctor name correctly (e.g., "Dr. Smith (Cardiology)" -> "Dr. Smith")
            doctor_name = doctor.split(" (")[0]
            
            # Get patient email if available
            patient_email = patient_info.get('Email') if patient_info else None
            
            result = appt_tool.book_appointment(selected_patient, datetime_str, doctor_name, reason, patient_email=patient_email)
            
            if result.get('success'):
                st.success(result.get('message'))
                st.json(result.get('booking'))
            else:
                st.error(f"Booking failed: {result.get('error')}")

# --- Page 4: Query Lab Reports ---
elif page == "🔬 Query Lab Reports":
    st.subheader("Query Lab Reports & Medical Knowledge")
    query = st.text_input("Enter your query about medical reports:")
    if st.button("Search"):
        if query:
            with st.spinner("Searching and structuring results..."):
                # 1. Get raw chunks
                raw_results = rag.query(query)
                
                # 2. Format with LLM
                if isinstance(raw_results, list) and raw_results:
                    context = "\n---\n".join(raw_results)
                    prompt = f"""
                    You are a medical research assistant. 
                    User Query: "{query}"
                    
                    Analyze the following document snippets and provide a structured answer.
                    
                    Return the output strictly as a JSON object with the following keys:
                    - "summary": A clear, direct answer to the query (string).
                    - "evidence": A list of objects, where each object has:
                        - "Source": The source or date of the info.
                        - "Excerpt": The relevant text snippet.
                        - "Context": Brief explanation of why it's relevant.
                    
                    Snippets:
                    {context}
                    """
                    try:
                        response = formatter_llm.invoke(prompt)
                        content = response.content
                        
                        # Attempt to parse JSON (handle potential markdown code blocks)
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                            
                        data = json.loads(content)
                        
                        st.markdown("### Search Results")
                        st.markdown(f"**Summary:** {data.get('summary')}")
                        
                        st.markdown("#### Evidence Table")
                        evidence = data.get('evidence', [])
                        if evidence:
                            st.table(pd.DataFrame(evidence))
                        else:
                            st.info("No specific evidence details found.")
                        
                        with st.expander("View Raw Source Text"):
                            st.write(raw_results)
                    except Exception as e:
                        st.error(f"Error formatting results: {e}")
                        st.write("Raw LLM Response:")
                        st.write(response.content)
                else:
                    st.warning("No relevant documents found.")
                    st.write(raw_results)
        else:
            st.warning("Please enter a query.")


