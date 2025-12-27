import pandas as pd
import os
from typing import Dict, Any, List, Optional

class EHRAdapter:
    def __init__(self, data_path: str = "data/records.xlsx"):
        self.data_path = data_path
        self._records = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_path):
            try:
                df = pd.read_excel(self.data_path)
                # Create a dictionary keyed by Name (lowercase for easier search)
                for _, row in df.iterrows():
                    # Handle potential NaN values
                    row_data = row.where(pd.notnull(row), None).to_dict()
                    if row_data.get('Name'):
                        name = row_data['Name'].lower()
                        self._records[name] = row_data
                        # Also index by first name for convenience
                        first_name = name.split()[0]
                        if first_name not in self._records:
                             self._records[first_name] = row_data
            except Exception as e:
                print(f"Error loading EHR data: {e}")
        else:
            print(f"Warning: EHR data file not found at {self.data_path}")

    def get_patient_summary(self, patient_name: str) -> Dict[str, Any]:
        return self._records.get(patient_name.lower(), {})

    def get_patient_history(self, patient_name: str) -> str:
        p = self.get_patient_summary(patient_name)
        if not p:
            return "Patient not found."
        
        summary = p.get('Summary', 'No summary available.')
        history = f"Patient: {p.get('Name')}, Age: {p.get('Age')}, Gender: {p.get('Gender')}.\nSummary: {summary}"
        return history

    def get_all_patient_names(self) -> List[str]:
        """Return a list of unique patient names."""
        # Filter out the first-name aliases by checking if the key matches the 'Name' field
        names = set()
        for key, data in self._records.items():
            if data.get('Name'):
                names.add(data['Name'])
        return list(names)

    def search_patients(self, keyword: str) -> List[Dict[str, Any]]:
        """Search for patients with a specific keyword in their summary."""
        results = []
        seen_names = set()
        keyword = keyword.lower()
        
        for key, data in self._records.items():
            # Avoid duplicates from aliases
            name = data.get('Name')
            if name and name not in seen_names:
                summary = str(data.get('Summary', '')).lower()
                if keyword in summary:
                    results.append(data)
                    seen_names.add(name)
        return results

    def append_note(self, patient_name: str, note: str, author: str = 'agent') -> Dict[str, Any]:
        # In a real app, this would write back to the DB/File
        # Here we just update the in-memory dict
        p = self.get_patient_summary(patient_name)
        if not p:
             return {'error': 'Patient not found'}
        
        notes = p.setdefault('notes', [])
        notes.append(f"[{author}]: {note}")
        return {'success': True}

    def add_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new patient and save to disk."""
        try:
            name = patient_data.get('Name')
            if not name:
                return {'success': False, 'error': 'Name is required'}
            
            # Update in-memory
            self._records[name.lower()] = patient_data
            first_name = name.split()[0].lower()
            self._records[first_name] = patient_data
            
            # Save to disk
            save_result = self._save_data()
            if save_result.get('success'):
                return {'success': True}
            else:
                return {'success': True, 'warning': f"Patient added to memory but save failed: {save_result.get('error')}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_patient(self, patient_name: str) -> bool:
        """Delete a patient and save to disk."""
        try:
            name_lower = patient_name.lower()
            if name_lower in self._records:
                del self._records[name_lower]
                
                # Also try to remove the first-name alias if it points to the same record
                first_name = name_lower.split()[0]
                if first_name in self._records:
                    del self._records[first_name]
                
                self._save_data()
                return True
            return False
        except Exception as e:
            print(f"Error deleting patient: {e}")
            return False

    def _save_data(self) -> Dict[str, Any]:
        """Persist current records to Excel."""
        try:
            # Convert dict back to list of dicts (deduplicating aliases)
            unique_records = {v['Name']: v for k, v in self._records.items()}.values()
            df = pd.DataFrame(list(unique_records))
            
            # Check if file is open/locked
            if os.path.exists(self.data_path):
                try:
                    os.rename(self.data_path, self.data_path)
                except OSError:
                    return {'success': False, 'error': 'File is open in another program. Please close records.xlsx and try again.'}
            
            df.to_excel(self.data_path, index=False)
            return {'success': True}
        except Exception as e:
            print(f"Error saving data: {e}")
            return {'success': False, 'error': str(e)}
        item = {'id': f'note-{len(notes)+1}', 'date': 'now', 'text': note, 'author': author}
        notes.append(item)
        return item
