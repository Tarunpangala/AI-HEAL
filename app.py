import os
import sqlite3
import streamlit as st
from datetime import datetime, time as dt_time, date, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import threading
import time
from plyer import notification

# Try to import pygame, but handle it gracefully if it fails
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configure Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("Gemini API key not found.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

class MedicalVaccineSystem:
    def __init__(self):
        # Initialize pygame mixer only if available
        self.sound_enabled = False
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
                self.sound_enabled = True
            except pygame.error:
                st.warning("Sound notifications are disabled: audio device not available")
        else:
            st.warning("Sound notifications are disabled: pygame not installed")
        
        self.comprehensive_vaccine_schedule = {
            "Newborn (Birth)": [
                {"name": "Hepatitis B", "description": "Protects against hepatitis B virus infection"},
                {"name": "BCG", "description": "Prevents tuberculosis"}
            ],
            "2 Months": [
                {"name": "RV (Rotavirus)", "description": "Prevents severe diarrhea from rotavirus"},
                {"name": "DTaP", "description": "Prevents diphtheria, tetanus, and pertussis"},
                {"name": "Hib", "description": "Prevents Haemophilus influenzae type b"},
                {"name": "PCV13", "description": "Prevents pneumococcal diseases"}
            ],
            "4-6 Months": [
                {"name": "Influenza", "description": "Annual flu vaccine"},
                {"name": "Additional DTaP", "description": "Booster for diphtheria, tetanus, and pertussis"}
            ],
            "12-15 Months": [
                {"name": "MMR", "description": "Prevents measles, mumps, and rubella"},
                {"name": "Varicella", "description": "Prevents chickenpox"}
            ],
            "4-6 Years": [
                {"name": "DTaP Booster", "description": "Continued protection against diphtheria, tetanus, and pertussis"},
                {"name": "MMR Booster", "description": "Additional MMR vaccine"}
            ],
            "11-12 Years": [
                {"name": "HPV", "description": "Prevents human papillomavirus"},
                {"name": "Tdap", "description": "Tetanus, diphtheria, and pertussis booster"}
            ],
            "Teens and Adults": [
                {"name": "Meningococcal", "description": "Prevents meningococcal diseases"},
                {"name": "Annual Flu", "description": "Yearly influenza vaccine"}
            ],
            "50+ Years": [
                {"name": "Shingles", "description": "Prevents shingles"},
                {"name": "Pneumococcal", "description": "Prevents pneumococcal diseases"}
            ]
        }
        
        self.conn = sqlite3.connect("medicine_reminders.db", check_same_thread=False)
        self.create_reminder_table()

        # Simplified alarm setup
        self.sound_file = "alarm.mp3"
        self.monitoring = True
        
        # Load sound file if pygame is available
        if self.sound_enabled and os.path.exists(self.sound_file):
            try:
                pygame.mixer.music.load(self.sound_file)
            except pygame.error as e:
                st.error(f"Error loading sound file: {e}")
                self.sound_enabled = False

        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_reminders, daemon=True)
        self.monitor_thread.start()

        # Create custom CSS
        self.create_custom_css()

    def create_custom_css(self):
        """Add custom CSS including the doctor-box style."""
        st.markdown("""
            <style>
            .title {
                text-align: center;
                color: #2e7d32;
                padding: 20px;
                animation: fadeIn 1.5s;
            }
            @keyframes fadeIn {
                0% {opacity: 0;}
                100% {opacity: 1;}
            }
            .card {
                border-radius: 10px;
                padding: 20px;
                margin: 10px 0;
                background-color: white;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                transition: transform 0.3s ease;
            }
            .card:hover {
                transform: translateY(-5px);
            }
            .metric-card {
                text-align: center;
                padding: 15px;
                border-radius: 8px;
                background: #f8f9fa;
                margin: 5px;
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                color: #2e7d32;
            }
            .health-tip {
                padding: 15px;
                border-left: 4px solid #2e7d32;
                background: #f1f8e9;
                margin: 10px 0;
            }
            .emergency-button {
                background-color: #ff4444;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                text-align: center;
                margin: 10px 0;
                cursor: pointer;
            }
            .doctor-box {
                background-color: #f0f8ff;
                padding: 20px;
                border-radius: 10px;
                border-left: 5px solid #0066cc;
                margin: 20px 0;
            }
            </style>
        """, unsafe_allow_html=True)

    def create_reminder_table(self):
        """Create reminders table if not exists."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_name TEXT NOT NULL,
                due_datetime TEXT NOT NULL,
                notified INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

    def notify_user(self, reminder_id, medicine_name, due_time):
        """Synchronized notification system."""
        try:
            # Play sound and show notification simultaneously
            def play_sound_and_notify():
                # Play sound if enabled
                if self.sound_enabled and os.path.exists(self.sound_file):
                    try:
                        pygame.mixer.music.play()
                    except pygame.error:
                        pass
                    
                # Show desktop notification
                try:
                    notification.notify(
                        title="Medicine Reminder",
                        message=f"Time to take: {medicine_name}\nScheduled for: {due_time}",
                        app_icon=None,
                        timeout=10
                    )
                except Exception as e:
                    st.error(f"Desktop notification error: {e}")
                
                # Wait for sound to finish if sound is enabled
                if self.sound_enabled:
                    time.sleep(5)
                    try:
                        pygame.mixer.music.stop()
                    except pygame.error:
                        pass

            # Execute notification in a separate thread
            notification_thread = threading.Thread(target=play_sound_and_notify)
            notification_thread.start()
            
            # Mark as notified
            self.mark_reminder_as_notified(reminder_id)
            return True
            
        except Exception as e:
            st.error(f"Notification error: {e}")
            return False

    def monitor_reminders(self):
        """Monitor reminders for notification."""
        while self.monitoring:
            try:
                cursor = self.conn.cursor()
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Get unnotified due reminders
                cursor.execute('''
                    SELECT id, medicine_name, due_datetime 
                    FROM reminders 
                    WHERE notified = 0 
                    AND datetime(due_datetime) <= datetime(?)
                ''', (current_time,))
                
                due_reminders = cursor.fetchall()
                
                for reminder in due_reminders:
                    reminder_id, medicine_name, due_time = reminder
                    self.notify_user(reminder_id, medicine_name, due_time)
                
            except sqlite3.Error as e:
                st.error(f"Database error in monitor_reminders: {e}")
            except Exception as e:
                st.error(f"Error in monitor_reminders: {e}")
            
            time.sleep(60)  # Check every minute

    def mark_reminder_as_notified(self, reminder_id):
        """Mark a reminder as notified."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE reminders SET notified = 1 WHERE id = ?', (reminder_id,))
        self.conn.commit()

    def set_vaccine_reminder(self):
        """Set medicine reminder with custom name input."""
        st.title("🔔 Set Medicine Reminder")
        
        with st.form("reminder_form"):
            # Custom medicine name input
            medicine_name = st.text_input("Enter Medicine Name", 
                                        placeholder="e.g., Aspirin, Paracetamol, etc.")
            
            col1, col2 = st.columns(2)
            with col1:
                reminder_date = st.date_input("Select Date", min_value=date.today())
            with col2:
                time_col1, time_col2, time_col3 = st.columns(3)
                with time_col1:
                    hour = st.selectbox("Hour", range(1, 13), format_func=lambda x: f"{x:02d}")
                with time_col2:
                    minute = st.selectbox("Minute", range(60), format_func=lambda x: f"{x:02d}")
                with time_col3:
                    period = st.selectbox("AM/PM", ["AM", "PM"])

            submit_button = st.form_submit_button("Set Reminder")

        if submit_button:
            if not medicine_name:
                st.error("Please enter a medicine name.")
                return
                
            # Convert to 24-hour format
            hour_24 = (hour % 12) + (12 if period == "PM" else 0)
            reminder_time = dt_time(hour_24, minute)
            reminder_datetime = datetime.combine(reminder_date, reminder_time)
            
            # Validate future date
            if reminder_datetime <= datetime.now():
                st.error("Please select a future date and time.")
                return
            
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO reminders (medicine_name, due_datetime, notified)
                    VALUES (?, ?, 0)
                ''', (medicine_name, reminder_datetime.strftime("%Y-%m-%d %H:%M:%S")))
                self.conn.commit()
                st.success(f"✅ Reminder set for {medicine_name} on {reminder_datetime.strftime('%Y-%m-%d %I:%M %p')}")
            except sqlite3.Error as e:
                st.error(f"Error setting reminder: {e}")

    def view_reminders(self):
        """View and manage reminders."""
        st.title("📆 My Medicine Reminders")

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, medicine_name, due_datetime, notified 
            FROM reminders 
            ORDER BY due_datetime ASC
        """)
        reminders = cursor.fetchall()

        if reminders:
            for reminder in reminders:
                reminder_id, medicine_name, due_time, notified = reminder
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{medicine_name}**")
                    with col2:
                        st.write(due_time)
                    with col3:
                        if st.button("Delete", key=f"del_{reminder_id}"):
                            self.delete_reminder(reminder_id)
                            st.rerun()
                st.divider()
        else:
            st.info("No reminders set. Add some reminders to get started!")

    def delete_reminder(self, reminder_id):
        """Delete a specific reminder."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
        self.conn.commit()
        st.success("Reminder deleted successfully!")

    def analyze_disease(self):
        """Virtual Doctor Emergency Guide."""
        st.title("🚨 Emergency First Aid Guide")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            emergency_input = st.text_input(
                "What's the emergency situation?",
                placeholder="e.g., deep cut, burn, sprain, allergic reaction, etc."
            )
            
            if st.button("Get Immediate Steps", type="primary"):
                if emergency_input:
                    with st.spinner("Getting immediate first aid steps..."):
                        prompt = f"""
                        As a professional emergency doctor, provide exactly 5-6 precise, clear steps for immediate first aid treatment for {emergency_input}.
                        Format the response as:
                        **Immediate Steps to Take:**
                        1. [First immediate action]
                        2. [Second immediate action]
                        3. [Third immediate action]
                        4. [Fourth immediate action]
                        5. [Fifth immediate action]
                        [Optional 6th step if critically needed]

                        Keep each step concise and actionable, focusing only on the most critical immediate actions needed.
                        """
                        
                        result = self.safe_generate_content(prompt)
                        if result:
                            st.markdown("<div class='doctor-box'>", unsafe_allow_html=True)
                            st.markdown(result)
                            st.markdown("</div>", unsafe_allow_html=True)
                            st.error("⚠️ **IMPORTANT:** This is first aid guidance only. For serious emergencies, call emergency services immediately!")
                else:
                    st.error("Please describe the emergency situation.")

    def analyze_tablet(self):
        """Medication analysis with AI."""
        st.title("💊 Medication Analysis")

        tablet_name = st.text_input("Enter Medication Name")
        
        if st.button("Analyze Medication"):
            if tablet_name:
                prompt = f"""Provide detailed information about {tablet_name} including:
                1. Classification and ingredients
                2. Uses and benefits
                3. Proper usage guidelines
                4. Precautions and side effects
                5. Storage requirements
                """

                with st.spinner("Analyzing medication..."):
                    result = self.safe_generate_content(prompt)
                    if result:
                        st.markdown(result)

    def vaccine_scheduler(self):
        """Interactive vaccine scheduler."""
        st.title("📅 Vaccine Schedule Guide")
        
        age_groups = list(self.comprehensive_vaccine_schedule.keys())
        selected_age = st.selectbox("Select Age Group", age_groups)
        
        if selected_age:
            st.subheader(f"Recommended Vaccines for {selected_age}")
            vaccines = self.comprehensive_vaccine_schedule[selected_age]
            
            for vaccine in vaccines:
                with st.expander(f"{vaccine['name']}"):
                    st.write(vaccine['description'])

    def safe_generate_content(self, prompt):
        """Generate AI content safely."""
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            st.error(f"Error generating content: {e}")
            return None

def create_home_page(system):
    """Create the home page."""
    st.markdown('<h1 class="title">🏥 Welcome to Your Health Companion</h1>', unsafe_allow_html=True)

    # Quick Actions Section
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.image("https://static.foxnews.com/foxnews.com/content/uploads/2021/05/child_vaccine_istock.jpg", use_column_width=True)
            st.subheader("📅 Set Medicine Reminder")
            st.write("Set up your medicine reminders with just a few clicks.")
            if st.button("Set Reminder", key="set_reminder"):
                st.session_state['navigation'] = "Set Medicine Reminder"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.image("https://tse4.mm.bing.net/th?id=OIP.mWvFMvKjNyhJuvLPg_PIygHaFS&pid=Api&P=0&h=180", use_column_width=True)
            st.subheader("🚨 Emergency Guide")
            st.write("Get quick first aid steps for emergency situations.")
            if st.button("Access Guide", key="emergency_guide"):
                st.session_state['navigation'] = "Emergency Guide"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.image("https://tse2.mm.bing.net/th?id=OIP.-I2zAZdJH3wddxk0t6a1fAAAAA&pid=Api&P=0&h=180", use_column_width=True)
            st.subheader("💊 Medication Info")
            st.write("Learn about your medications and their effects.")
            if st.button("Check Medication", key="check_medication"):
                st.session_state['navigation'] = "Medication Analysis"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Health Tips Section
    st.markdown("### 💡 Daily Health Tips")
    with st.container():
        st.markdown('<div class="health-tip">', unsafe_allow_html=True)
        st.markdown("**Tip of the Day:** It is health that is real wealth and not pieces of gold and silver.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Emergency Section
    st.markdown("### 🚨 Emergency Resources")
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Emergency Contact:** 108")
        st.markdown("**24/7 Health Helpline:**")
        st.markdown("**Ambulance Service:** 108")
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    # Initialize session state
    if 'navigation' not in st.session_state:
        st.session_state['navigation'] = "Home"

    # Initialize the system
    system = MedicalVaccineSystem()

    # Sidebar navigation
    st.sidebar.title("Navigation")
    navigation_options = {
        "Home": "🏠",
        "Set Medicine Reminder": "🔔",
        "View Reminders": "📆",
        "Emergency Guide": "🚨",
        "Medication Analysis": "💊",
        "Vaccine Schedule": "📅"
    }

    # Create navigation buttons
    for page, icon in navigation_options.items():
        if st.sidebar.button(f"{icon} {page}"):
            st.session_state['navigation'] = page
            st.rerun()

    # Page routing
    current_page = st.session_state['navigation']
    
    if current_page == "Home":
        create_home_page(system)
    elif current_page == "Set Medicine Reminder":
        system.set_vaccine_reminder()
    elif current_page == "View Reminders":
        system.view_reminders()
    elif current_page == "Emergency Guide":
        system.analyze_disease()
    elif current_page == "Medication Analysis":
        system.analyze_tablet()
    elif current_page == "Vaccine Schedule":
        system.vaccine_scheduler()

if __name__ == "__main__":
    st.set_page_config(
        page_title="Health Companion",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    main()