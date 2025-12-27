from typing import Dict, Any, List, Optional
import uuid
import datetime
from tools.email_tool import EmailTool

class AppointmentAdapter:
    def __init__(self):
        # provider schedules: doctor_id -> list of slot dicts
        self._schedules: Dict[str, List[Dict[str, Any]]] = {}
        self._bookings: Dict[str, Dict[str, Any]] = {}
        self.email_tool = EmailTool()
        # Initialize with some dummy data
        self._init_dummy_data()

    def _init_dummy_data(self):
        self.add_availability("dr_nephrologist", [
            {"id": "slot1", "start": "2025-01-02T09:00:00", "end": "2025-01-02T09:30:00", "booked": False},
            {"id": "slot2", "start": "2025-01-02T10:00:00", "end": "2025-01-02T10:30:00", "booked": False},
        ])
        self.add_availability("dr_gp", [
            {"id": "slot3", "start": "2025-01-03T09:00:00", "end": "2025-01-03T09:30:00", "booked": False},
        ])

    def add_availability(self, doctor_id: str, slots: List[Dict[str, Any]]):
        self._schedules.setdefault(doctor_id, []).extend(slots)

    def get_availability(self, doctor_id: str, start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
        # In a real app, filter by start/end
        return [s for s in self._schedules.get(doctor_id, []) if not s.get('booked')]

    def book_appointment(self, patient_id: str, time: str, doctor_id: str, reason: str = '', patient_email: str = None) -> Dict[str, Any]:
        """
        Book an appointment.
        For this demo, we accept a time string directly and simulate a successful booking
        if the doctor is available (or just always success for demo purposes).
        """
        # Simulate creating a slot on the fly for the requested time
        booking_id = str(uuid.uuid4())
        
        # Create a mock slot for this booking
        slot = {
            "id": str(uuid.uuid4()),
            "start": time,
            "end": "30 mins later",
            "booked": True
        }
        
        booking = {
            'booking_id': booking_id, 
            'patient_id': patient_id, 
            'doctor_id': doctor_id, 
            'slot': slot, 
            'reason': reason,
            'status': 'confirmed'
        }
        
        self._bookings[booking_id] = booking
        
        # Send Email Confirmation
        email_status = "Email not sent (no recipient provided)"
        if patient_email:
            subject = f"Appointment Confirmation: {doctor_id} at {time}"
            body = f"""
            Dear {patient_id},
            
            Your appointment has been confirmed.
            
            Doctor: {doctor_id}
            Time: {time}
            Reason: {reason}
            Booking ID: {booking_id}
            
            Please arrive 10 minutes early.
            
            Best regards,
            AI Medical Assistant
            """
            email_res = self.email_tool.send_email(patient_email, subject, body)
            if email_res.get('success'):
                email_status = "Email confirmation sent."
            else:
                email_status = f"Failed to send email: {email_res.get('error')}"
        
        return {
            'success': True, 
            'message': f"Appointment confirmed for {patient_id} with {doctor_id} at {time}. {email_status}",
            'booking': booking
        }

    def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        b = self._bookings.pop(booking_id, None)
        if not b:
            return {'success': False, 'error': 'not-found'}
        doc_slots = self._schedules.get(b['doctor_id'], [])
        s = next((sl for sl in doc_slots if sl.get('id') == b['slot'].get('id')), None)
        if s:
            s['booked'] = False
        return {'success': True}
