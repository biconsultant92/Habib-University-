import streamlit as st
import pandas as pd
import datetime
import time
from db_connection import fetch_data
from streamlit_autorefresh import st_autorefresh

# Importing Backend Logic Files
import faculty_backend as fb
import student_backend as sb
from availability_logic import calculate_availability # needed for specific UI calculation steps

# ==========================================
# PAGE CONFIGURATION & CSS
# ==========================================
st.set_page_config(
    page_title="HU Office Hours Portal", 
    page_icon="🎓", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Button Hover Effects */
    .stButton>button {
        transition: all 0.3s ease-in-out;
        border-radius: 8px;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
    /* Profile Bar Styling */
    .profile-container {
        padding: 10px;
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'show_welcome_toast' not in st.session_state:
    st.session_state.show_welcome_toast = False

# ==========================================
# LOGIN & LOGOUT UI LOGIC
# ==========================================
def login():
    st.write("")
    st.write("")
    
    # Header
    st.markdown("<h1 style='text-align: center; color: #1E88E5;'>🎓 Office Hours Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray; font-size: 18px;'>Connect with your faculty efficiently & seamlessly.</p>", unsafe_allow_html=True)
    st.write("---")
    
    # Adjusted column ratio for a better-centered login card
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center;'>🔐 Secure Login</h3>", unsafe_allow_html=True)
            st.write("")
            
            #  Press Enter Feature
            with st.form(key="login_form", clear_on_submit=False):
                user_id_input = st.text_input(
                    "👤 Enter your ID", 
                    placeholder="e.g., 00712 (Faculty) or 17432 (Student)",
                    help="Type your ID and press Enter to login."
                )
                
                st.write("") # Little spacing
                submit_button = st.form_submit_button("Login", type="primary", use_container_width=True)
            
            # Form submission logic
            if submit_button:
                if user_id_input.strip(): # .strip() removes accidental spaces
                    with st.spinner("Authenticating securely..."):
                        time.sleep(0.5) 
                        
                        query = "SELECT UserID, FullName, Role, Program FROM Users WHERE UserID = ?"
                        df_user = fetch_data(query, (user_id_input.strip(),))
                        
                        if not df_user.empty:
                            st.session_state.logged_in = True
                            st.session_state.user_data = df_user.iloc[0].to_dict()
                            st.session_state.show_welcome_toast = True 
                            st.rerun()
                        else:
                            st.error(" Invalid ID. User not found. Please try again.")
                else:
                    st.warning(" Please enter an ID to login.")
                    
    # Subtle footer hint
    st.markdown("<p style='text-align: center; color: #D3D3D3; font-size: 13px; margin-top: 20px;'>Authorized Personnel Only</p>", unsafe_allow_html=True)


def logout():
    st.session_state.logged_in = False
    st.session_state.user_data = None
    st.session_state.show_welcome_toast = False
    st.rerun()

# ==========================================
# FACULTY UI SECTION
# ==========================================
def render_faculty_ui(user_id, full_name, program):
    st.divider()

    # Backend se options lana
    base_venue_options = fb.get_faculty_venues(full_name)
    tab1, tab2 = st.tabs(["🗓️ Schedule New Office Hours", "📋 My Scheduled Hours & Exceptions"])

    # --- FACULTY: TAB 1 ---
    with tab1:
            st.subheader("Plan Your Upcoming Availability")
            
            #  Session State Flags & Default Times
            if "avail_checked" not in st.session_state:
                st.session_state.avail_checked = False
            
            # Flag to manage suggestions visibility
            if "show_suggestions" not in st.session_state:
                st.session_state.show_suggestions = True
            
            if "selected_start" not in st.session_state:
                st.session_state.selected_start = "01:00 PM"
            if "selected_end" not in st.session_state:
                st.session_state.selected_end = "02:00 PM"

            # Bring back suggestions when manual check is triggered
            def trigger_check():
                st.session_state.avail_checked = True
                st.session_state.show_suggestions = True 

            def reset_check():
                st.session_state.avail_checked = False

            # Hide suggestions block after selecting a slot
            def apply_suggestion(suggested_start, suggested_end):
                st.session_state.selected_start = suggested_start
                st.session_state.selected_end = suggested_end
                st.session_state.avail_checked = True  
                st.session_state.show_suggestions = False 
                st.toast(f"✅ Slot updated to {suggested_start} - {suggested_end}!") 

            # ==========================================
            # 1. SCOPE SELECTION
            # ==========================================
            with st.container(border=True):
                st.markdown("#### 1. Who are you scheduling for?")
                
                safe_program = str(program).strip() if pd.notna(program) else ""
                has_valid_program = safe_program != "" and safe_program.lower() != "none"
                
                if has_valid_program:
                    booking_scope = st.radio("Select Scope", ["Program", "Course"], horizontal=True, label_visibility="collapsed", on_change=reset_check)
                else:
                    st.info("ℹ️ You are not assigned to a specific program. Defaulting to Course selection.")
                    booking_scope = "Course"
                
                scope_value = safe_program 
                
                if booking_scope == "Course":
                    course_dict = fb.get_faculty_courses(user_id) 
                    if course_dict:
                        selected_course_names = st.multiselect("Select Your Course(s)", list(course_dict.keys()), on_change=reset_check)
                        scope_value = selected_course_names 
                    else:
                        st.warning("No courses assigned to you in the current semester data.")
                        scope_value = [] 

            selected_term_label = "Regular Schedule"
            selected_term = "NULL"

            # Dynamic step numbering to keep UI clean
            step_num = 2 

            # ==========================================
            # 2. SESSION FREQUENCY (Conditional)
            # ==========================================
            if booking_scope == "Course":
                with st.container(border=True):
                    st.markdown(f"#### {step_num}. Session Frequency")
                    booking_frequency = st.radio("Booking Type:", ["Whole Semester", "Specific Date(s)"], horizontal=True, on_change=reset_check)
                step_num += 1
            else:
                # If Program is selected, default to Whole Semester and hide the UI
                booking_frequency = "Whole Semester"


            # ==========================================
            # 3. WHEN IS THE SESSION (Dynamic Inputs)
            # ==========================================
            with st.container(border=True):
                st.markdown(f"#### {step_num}. When is the session?")
                
                specific_dates = []
                day_of_week = "Monday" # Default fallback
                
                # Dynamic Render: Show Dropdown OR Calendar based on Frequency selection
                if booking_frequency == "Whole Semester":
                    day_of_week = st.selectbox("Day of Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], on_change=reset_check)
                else:
                    #  Shows a standard Calendar to pick a specific date
                    #  Here is the  validation Minimum date 'tomorrow'
                    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
                    
                    selected_date = st.date_input(
                        "Select Specific Date from Calendar", 
                        value=tomorrow,       # Default calendar open tomorrow 
                        min_value=tomorrow,   # disable Past dates and today 
                        on_change=reset_check
                    )
                    
                    if selected_date:
                        # Automatically extract the day of the week from the chosen calendar date for the backend logic
                        day_of_week = selected_date.strftime("%A") 
                        specific_dates = [selected_date.strftime("%Y-%m-%d")]
                        st.info(f"📅 You selected **{day_of_week}**, {selected_date.strftime('%B %d, %Y')}")

                
                # Time Selection
                col1, col2 = st.columns(2)
                time_options = fb.get_time_slots()
                with col1:
                    start_time_str = st.selectbox("Start Time", time_options, key="selected_start", on_change=reset_check)
                with col2:
                    end_time_str = st.selectbox("End Time", time_options, key="selected_end", on_change=reset_check)
                
                start_time_obj = datetime.datetime.strptime(start_time_str, "%I:%M %p").time()
                end_time_obj = datetime.datetime.strptime(end_time_str, "%I:%M %p").time()
                
                # Duration Calculation
                start_dt = datetime.datetime.combine(datetime.date.today(), start_time_obj)
                end_dt = datetime.datetime.combine(datetime.date.today(), end_time_obj)
                duration_min = int((end_dt - start_dt).total_seconds() / 60)

                st.write("") 
                st.button("🔍 Check Student Availability", use_container_width=True, type="primary", on_click=trigger_check)

                if st.session_state.avail_checked:
                    # Validations
                    if start_time_obj >= end_time_obj:
                        st.error("⚠️ Start time must be before End time.")
                    elif duration_min < 30:
                        st.error(f"⚠️ **Invalid Duration:** You have selected a {duration_min}-minute slot. Office hours must be at least **30 minutes** long.")
                    elif booking_scope == "Course" and not scope_value:
                        st.error("Please select at least one course to continue.")
                    elif booking_frequency == "Specific Date(s)" and not specific_dates:
                        st.error("Please select a valid date from the calendar to check availability.")
                    else:
                        with st.spinner("Analyzing student schedules and finding best slots..."):
                            term_condition = "" 
                            df_schedule = fb.fetch_student_schedules_for_booking(booking_scope, scope_value, program, term_condition)
                            
                            if not df_schedule.empty:
                                count, percent = calculate_availability(
                                    df_schedule, day_of_week, start_time_obj, end_time_obj, selected_term,
                                    booking_frequency=booking_frequency, specific_dates=specific_dates
                                )
                                
                                try:
                                    total_students = int(round((count * 100) / float(percent))) if percent > 0 else count
                                    student_text = f"{count} out of {total_students} students"
                                except ZeroDivisionError:
                                    student_text = f"{count} students" 
                                
                                freq_text = "for the Whole Semester" if booking_frequency == "Whole Semester" else f"on {specific_dates[0]}"
                                st.success(f"✅ **{percent}%** ({student_text}) have a free **{duration_min}-minute** window on **{day_of_week}** ({freq_text})!")

                                # Alternative Suggestions Logic
                                if st.session_state.show_suggestions:
                                    all_suggestions = fb.generate_alternative_suggestions(
                                        df_schedule, day_of_week, start_time_obj, end_time_obj, selected_term, 0,
                                        booking_frequency=booking_frequency, specific_dates=specific_dates
                                    )
                                    
                                    st.divider()
                                    st.markdown("### 💡 Alternative Suggestions")
                                    st.caption("Click on any suggestion below to select it as your time slot.")
                                    
                                    default_target = percent if percent > 0 else 60
                                    
                                    with st.expander("⚙️ Custom Suggestions Filter (Optional)", expanded=False):
                                        with st.form("filter_suggestions_form"):
                                            st.markdown("Customize to find specific availability (e.g., `<= 60%` or exactly `100%`):")
                                            col_s1, col_s2, col_s3 = st.columns(3)
                                            with col_s1:
                                                op_choice = st.selectbox("Availability Should Be:", [">=", "<=", "=="], index=0, format_func=lambda x: {">=": "Greater than or equal (>=)", "<=": "Less than or equal (<=)", "==": "Exactly (==)"}[x])
                                            with col_s2:
                                                target_avail = st.number_input("Target Percentage (%)", min_value=0, max_value=100, value=int(default_target), step=5)
                                            with col_s3:
                                                num_slots_filter = st.number_input("Number of Suggestions", min_value=1, max_value=10, value=3)
                                            
                                            apply_filter_btn = st.form_submit_button("🛠️ Apply Filter")

                                    filtered_suggestions = []
                                    if all_suggestions:
                                        for s in all_suggestions:
                                            if s['start_str'] == start_time_str and s['end_str'] == end_time_str:
                                                continue
                                                
                                            if op_choice == ">=" and s['percent'] >= target_avail:
                                                filtered_suggestions.append(s)
                                            elif op_choice == "<=" and s['percent'] <= target_avail:
                                                filtered_suggestions.append(s)
                                            elif op_choice == "==" and s['percent'] == target_avail:
                                                filtered_suggestions.append(s)
                                                
                                        final_suggestions = filtered_suggestions[:int(num_slots_filter)]
                                        
                                        if final_suggestions:
                                            if len(final_suggestions) < int(num_slots_filter):
                                                st.caption(f"ℹ️ Found only {len(final_suggestions)} slot(s) matching your criteria.")
                                                
                                            for s in final_suggestions:
                                                try:
                                                    tot = int(round((s['count'] * 100) / float(s['percent']))) if s['percent'] > 0 else s['count']
                                                    s_text = f"{s['count']} out of {tot}"
                                                except ZeroDivisionError:
                                                    s_text = str(s['count'])
                                                
                                                btn_label = f"🕒 {s['start_str']} to {s['end_str']} — {s['percent']}% ({s_text} students available)"
                                                st.button(btn_label, key=f"btn_{s['start_str']}_{s['end_str']}", use_container_width=True, on_click=apply_suggestion, args=(s['start_str'], s['end_str']))
                                                
                                        else:
                                            st.warning(f"⚠️ No alternative slots found matching: **{op_choice} {target_avail}%** for a {duration_min}-minute duration.")
                                    else:
                                        st.caption("No alternative slots could be generated for this day.")
                            else:
                                st.warning("No student schedule data found for this selection. (Check if students are registered in this program/course)")

            step_num += 1

            # ==========================================
            # 4. VENUE SETUP & SAVE BUTTON
            # ==========================================
            with st.container(border=True):
                st.markdown(f"#### {step_num}. Where will it be?")
                
                selected_venue = st.selectbox("Select Venue", base_venue_options)
                final_venue = selected_venue
                meeting_link = ""
                
                if selected_venue == "Online":
                    meeting_link = st.text_input("🔗 Enter Meeting Link (Zoom/Teams):", placeholder="Paste your meeting link here...")
                elif selected_venue == "Other":
                    final_venue = st.text_input("📝 Please enter your custom venue or room number:", placeholder="e.g., Library Pod, Room 102")
                st.write("") 
                
                if st.button("💾 Confirm & Save Schedule", use_container_width=True, type="secondary"):
                    if start_time_obj >= end_time_obj:
                        st.error("⚠️ Start time must be before End time.")
                    elif duration_min < 60:
                        st.error(f"⚠️ **Cannot Save:** Office hours must be at least **60 minutes** long.")
                    elif booking_scope == "Course" and not scope_value:
                        st.error("Cannot save. Please select at least one course.")
                    elif booking_frequency == "Specific Date(s)" and not specific_dates:
                        st.error("Cannot save. Please select a specific date.")
                    elif selected_venue == "Other" and not final_venue.strip():
                        st.error("Please enter a custom venue before saving.")
                    elif selected_venue == "Online" and not meeting_link.strip():
                        st.error("Please provide a meeting link for the online session.")
                    else:
                        db_term = None if selected_term == "NULL" else selected_term
                        
                        success = fb.save_base_schedule(
                            user_id, booking_scope, scope_value, day_of_week, start_time_obj, end_time_obj, 
                            final_venue, meeting_link, db_term,
                            booking_frequency=booking_frequency, specific_dates=specific_dates
                        )
                        
                        if success:
                            st.balloons() 
                            st.success(f"🎉 Office hours saved successfully for **{selected_term_label}** at **{final_venue}**!")
                            st.session_state.avail_checked = False
                        else:
                            st.error("Failed to save schedule. Check database connection.")
    
    #------------------------
    # FACULTY: TAB 2
    #------------------------
    with tab2:
        st.subheader("📋 Your Base Semester Schedule")
        
        # Backend call
        df_my_schedule = fb.get_my_base_schedules(user_id) 
        
        if not df_my_schedule.empty:
            # Clean up the dataframe for display
            display_df = df_my_schedule.drop(columns=['Schedule_ID'])
            display_df.columns = ['Day', 'Term Period', 'Start Time', 'End Time', 'Scope', 'Course/Program', 'Venue', 'Link']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.write("---")
            
            # Management Section Header
            st.subheader("⚙️ Manage & Adjust Slots")
            st.markdown("<p style='color: gray; font-size: 14px;'>Cancel or reschedule an upcoming session, or make permanent changes to your semester schedule.</p>", unsafe_allow_html=True)
            st.write("")
            
            # MAIN CONTROL PANEL
            with st.container(border=True):
                # Format schedule options for the dropdown
                schedule_options = []
                for index, row in df_my_schedule.iterrows():
                    label = f"{row['Day_of_Week']} ({row['MEETING_DESCR']}) - {row['Booking_Scope']} {row['Scope_Value']} ({row['Start_Time']} to {row['End_Time']})"
                    db_term_value = "NULL" if row['MEETING_DESCR'] == "Regular Schedule" else row['MEETING_DESCR']
                    schedule_options.append((row['Schedule_ID'], label, row['Day_of_Week'], row['Booking_Scope'], row['Scope_Value'], db_term_value))
                
                sched_dict = {label: (sched_id, day, b_scope, s_value, term) for sched_id, label, day, b_scope, s_value, term in schedule_options}
                
                # STEP 1
                st.markdown("#### **Step 1:** Select a Slot")
                selected_label = st.selectbox("Choose the regular office hour slot you want to modify:", list(sched_dict.keys()), label_visibility="collapsed")
                selected_schedule_id, expected_day, res_scope, res_scope_value, res_term = sched_dict[selected_label]
                
                st.write("")
                
                # STEP 2
                st.markdown("#### **Step 2:** Choose Change Type")
                change_scope = st.radio("Is this a one-time change or a permanent update?", 
                                        ["Single specific date (e.g., taking a day off)", "Permanently (Update the rest of the semester)"], 
                                        horizontal=False, 
                                        label_visibility="collapsed")
                
                st.divider()

                # ==========================================
                # BRANCH A: SINGLE SPECIFIC DATE
                # ==========================================
                if change_scope == "Single specific date (e.g., taking a day off)":
                    
                    st.markdown(f"#### **Step 3:** Specific Date Details")
                    
                    # Calculate next valid dates based on the selected day of the week
                    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    today = datetime.date.today()
                    target_day_idx = days_of_week.index(expected_day)
                    days_ahead = target_day_idx - today.weekday()
                    if days_ahead < 0:
                        days_ahead += 7 
                        
                    first_valid_date = today + datetime.timedelta(days=days_ahead)
                    valid_dates = [first_valid_date + datetime.timedelta(weeks=i) for i in range(10)]
                    date_options = {d.strftime("%A, %d %b %Y"): d for d in valid_dates}
                    
                    sd_col1, sd_col2 = st.columns(2)
                    with sd_col1:
                        st.markdown(f"**Target Date ({expected_day}):**")
                        selected_date_label = st.selectbox("Choose valid date", list(date_options.keys()), label_visibility="collapsed")
                        target_date = date_options[selected_date_label] 
                        
                    with sd_col2:
                        st.markdown("**Action Required:**")
                        action_type = st.radio("Action", ["Cancel this date", "Reschedule / Change Venue"], label_visibility="collapsed")
                    
                    new_date, new_start_obj, new_end_obj, new_venue, new_link = None, None, None, None, None
                    
                    # Sub-branch: Rescheduling a Single Date
                    if action_type == "Reschedule / Change Venue":
                        with st.container(border=True):
                            st.markdown(f"##### 🔄 New Configuration for {target_date.strftime('%d %b')}")
                            new_date = st.date_input("Select New Date:", value=target_date)
                            new_day_name = new_date.strftime("%A")
                            
                            r_col1, r_col2 = st.columns(2)
                            time_options = fb.get_time_slots()
                            
                            with r_col1:
                                res_start = st.selectbox("New Start Time", time_options, key="res_s")
                                res_end = st.selectbox("New End Time", time_options, key="res_e")
                                new_start_obj = datetime.datetime.strptime(res_start, "%I:%M %p").time()
                                new_end_obj = datetime.datetime.strptime(res_end, "%I:%M %p").time()
                                
                                st.write("")
                                if st.button("🔍 Check Student Availability", key="res_avail_btn", use_container_width=True):
                                    if new_start_obj >= new_end_obj:
                                        st.error("⚠️ Start time must be before End time.")
                                    else:
                                        with st.spinner("Analyzing student schedules..."):
                                            res_term_condition = "" 
                                            df_res_schedule = fb.fetch_student_schedules_for_booking(res_scope, res_scope_value, program, res_term_condition)
                                            if not df_res_schedule.empty:
                                                count, percent = calculate_availability(df_res_schedule, new_day_name, new_start_obj, new_end_obj, res_term)
                                                st.success(f"✅ **{percent}%** available on **{new_day_name}** ({res_start} - {res_end})!")
                                                
                                                top_suggestions = fb.generate_alternative_suggestions(df_res_schedule, new_day_name, new_start_obj, new_end_obj, res_term, percent)
                                                if top_suggestions:
                                                    st.markdown("💡 **Alternative Time Suggestions:**")
                                                    for s in top_suggestions:
                                                        tot = int(round((s['count'] * 100) / float(s['percent']))) if s['percent'] > 0 else s['count']
                                                        st.info(f"🕒 **{s['start_str']} to {s['end_str']}** — **{s['percent']}%** ({s['count']} out of {tot} available)")
                                            else:
                                                st.warning("No student schedule data found.")

                            with r_col2:
                                res_selected_venue = st.selectbox("Select New Venue", base_venue_options, key="res_v")
                                new_venue = res_selected_venue
                                new_link = ""
                                if res_selected_venue == "Online":
                                    new_link = st.text_input("🔗 Enter Meeting Link", key="res_l1")
                                elif res_selected_venue == "Other":
                                    new_venue = st.text_input("📝 Enter Custom Venue/Room", key="res_v_other")

                    # Apply Changes Button (Single Date)
                    st.write("")
                    btn_label = "🚫 Confirm Cancellation" if action_type == "Cancel this date" else "💾 Apply Reschedule"
                    btn_type = "primary" if action_type == "Reschedule / Change Venue" else "secondary"
                    
                    if st.button(btn_label, type=btn_type, use_container_width=True):
                        if action_type == "Reschedule / Change Venue" and new_start_obj >= new_end_obj:
                            st.error("⚠️ Start time must be before End time.")
                        elif action_type == "Reschedule / Change Venue" and res_selected_venue == "Other" and not new_venue.strip():
                            st.error("⚠️ Please enter a custom venue before saving.")
                        elif action_type == "Reschedule / Change Venue" and res_selected_venue == "Online" and not new_link.strip():
                            st.error("⚠️ Please provide a meeting link for the online session.")
                        else:
                            status = "Cancelled" if action_type == "Cancel this date" else "Rescheduled"
                            success = fb.save_single_date_exception(selected_schedule_id, target_date, status, new_date, new_start_obj, new_end_obj, new_venue, new_link)
                            if success:
                                if status == "Cancelled":
                                    st.success(f"✅ Session successfully cancelled for **{target_date.strftime('%d %b %Y')}**.")
                                else:
                                    st.success(f"✅ Session rescheduled to **{new_date.strftime('%d %b')}** at {res_start}.")
                                time.sleep(1.5)
                                st.rerun() 
                            else:
                                st.error("❌ Failed to apply changes. Ensure database connection is stable.")


                # ==========================================
                # BRANCH B: PERMANENT CHANGE
                # ==========================================
                elif change_scope == "Permanently (Update the rest of the semester)":
                    
                    st.markdown("#### **Step 3:** Permanent Action")
                    action_type_perm = st.radio("What do you want to do?", 
                                                ["Cancel this slot completely", "Update Day / Time / Venue"], 
                                                horizontal=True,
                                                label_visibility="collapsed")
                    st.write("")
                    
                    # Sub-branch: Cancel Permanently
                    if action_type_perm == "Cancel this slot completely":
                        st.error(f"🚨 **WARNING:** This will permanently remove the **{expected_day}** session from your base schedule for the rest of the term.")
                        if st.button("🗑️ Confirm Permanent Cancellation", type="primary", use_container_width=True):
                            success = fb.cancel_permanent_schedule(selected_schedule_id)
                            if success:
                                st.success("✅ Slot permanently cancelled.")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("❌ Failed to cancel slot. Check database connection.")
                                
                    # Sub-branch: Update Permanently
                    elif action_type_perm == "Update Day / Time / Venue":
                        with st.container(border=True):
                            st.markdown("##### 🔄 New Permanent Details")
                            days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                            new_day_perm = st.selectbox("Select New Day", days_of_week, index=days_of_week.index(expected_day))
                            
                            p_col1, p_col2 = st.columns(2)
                            time_options = fb.get_time_slots()
                            
                            with p_col1:
                                perm_start = st.selectbox("New Start Time", time_options, key="perm_s")
                                perm_end = st.selectbox("New End Time", time_options, key="perm_e")
                                perm_start_obj = datetime.datetime.strptime(perm_start, "%I:%M %p").time()
                                perm_end_obj = datetime.datetime.strptime(perm_end, "%I:%M %p").time()
                                
                                st.write("")
                                if st.button("🔍 Check Student Availability", key="perm_avail_btn", use_container_width=True):
                                    if perm_start_obj >= perm_end_obj:
                                        st.error("⚠️ Start time must be before End time.")
                                    else:
                                        with st.spinner("Analyzing student schedules..."):
                                            res_term_condition = "" 
                                            df_res_schedule = fb.fetch_student_schedules_for_booking(res_scope, res_scope_value, program, res_term_condition)
                                            if not df_res_schedule.empty:
                                                count, percent = calculate_availability(df_res_schedule, new_day_perm, perm_start_obj, perm_end_obj, res_term)
                                                st.success(f"✅ **{percent}%** available on **{new_day_perm}** ({perm_start} - {perm_end})!")
                                                
                                                top_suggestions = fb.generate_alternative_suggestions(df_res_schedule, new_day_perm, perm_start_obj, perm_end_obj, res_term, percent)
                                                if top_suggestions:
                                                    st.markdown("💡 **Alternative Time Suggestions:**")
                                                    for s in top_suggestions:
                                                        tot = int(round((s['count'] * 100) / float(s['percent']))) if s['percent'] > 0 else s['count']
                                                        st.info(f"🕒 **{s['start_str']} to {s['end_str']}** — **{s['percent']}%** ({s['count']} out of {tot} available)")
                                            else:
                                                st.warning("No student schedule data found.")
                            
                            with p_col2:
                                perm_selected_venue = st.selectbox("Select New Venue", base_venue_options, key="perm_v")
                                new_venue_perm = perm_selected_venue
                                new_link_perm = ""
                                if perm_selected_venue == "Online":
                                    new_link_perm = st.text_input("🔗 Enter Meeting Link", key="perm_l1")
                                elif perm_selected_venue == "Other":
                                    new_venue_perm = st.text_input("📝 Enter Custom Venue/Room", key="perm_v_other")

                        # Apply Changes Button (Permanent Update)
                        st.write("")
                        if st.button("💾 Save Permanent Changes", type="primary", use_container_width=True):
                            if perm_start_obj >= perm_end_obj:
                                st.error("⚠️ Start time must be before End time.")
                            elif perm_selected_venue == "Other" and not new_venue_perm.strip():
                                st.error("⚠️ Please enter a custom venue before saving.")
                            elif perm_selected_venue == "Online" and not new_link_perm.strip():
                                st.error("⚠️ Please provide a meeting link for the online session.")
                            else:
                                success = fb.update_permanent_schedule(new_day_perm, perm_start_obj, perm_end_obj, new_venue_perm, new_link_perm, selected_schedule_id)
                                if success:
                                    st.success("✅ Base schedule updated permanently!")
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to update schedule. Ensure database connection is stable.")
        else:
            st.info("ℹ️ You haven't scheduled any office hours yet. Go to the 'Schedule New Office Hours' tab to book your slots.")

# ==========================================
# STUDENT UI SECTION
# ==========================================
def render_student_ui(user_id, full_name, program):
    st.divider()

    # --- 1. CALL BACKEND DATA ---
    df_my_program, df_other_programs, df_exceptions, df_student_courses = sb.get_student_dashboard_data(program, user_id)

    # --- 2. DISPLAY ENROLLED COURSES (Clean Grid View) ---
    if not df_student_courses.empty:
        with st.container(border=True):
            st.markdown("### 📚 Your Enrolled Courses")
            st.markdown("<p style='color: gray; font-size: 14px;'>Courses you are registered for this semester.</p>", unsafe_allow_html=True)
            
            # Use columns to create a neat 3-column grid for courses instead of mixing them in one line
            courses = df_student_courses['Course_Name'].tolist()
            cols = st.columns(3)
            for i, course in enumerate(courses):
                # Distribute courses evenly across the 3 columns
                with cols[i % 3]:
                    st.success(f"🎓 **{course}**")
    else:
        st.info("ℹ️ No active course enrollments found for your profile.")
        
    st.write("") # Spacing

    # --- 3. FETCH DATA FOR FILTERS ---
    try:
        from db_connection import fetch_data 
        all_progs_df = fetch_data("SELECT DISTINCT Program FROM Users WHERE Program IS NOT NULL AND Program != ''")
        all_courses_df = fetch_data("SELECT DISTINCT DESCR FROM PSCS_Course_2611_term WHERE DESCR IS NOT NULL AND DESCR != ''")
        
        # Clean and split comma-separated programs 
        raw_programs = all_progs_df['Program'].dropna().tolist() if not all_progs_df.empty else []
        cleaned_programs = set()
        
        for prog in raw_programs:
            for p in str(prog).split(','):
                clean_p = p.strip()
                if clean_p:
                    cleaned_programs.add(clean_p)
                    
        db_all_programs = sorted(list(cleaned_programs))
        db_all_courses = sorted(all_courses_df['DESCR'].dropna().unique().tolist()) if not all_courses_df.empty else []
        
    except Exception as e:
        # Fallback to empty lists if database fetch fails
        db_all_programs = []
        db_all_courses = []

    # --- 4. RENDER TAB CONTENT & CARDS ---
    def render_tab_content(df_schedules, tab_key):
        
        # Filter Section
        with st.expander("🔍 Filter Office Hours", expanded=False):
            col_f1, col_f2, col_f3 = st.columns(3)
            
            with col_f1:
                all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                selected_days = st.multiselect("🗓️ Filter by Day", all_days, key=f"day_{tab_key}")
                
            with col_f2:
                all_types = ["Program", "Course"]
                selected_types = st.multiselect("📌 Scope Type", all_types, key=f"type_{tab_key}", placeholder="Select Scope")
                
            with col_f3:
                # Dynamic List based on Type Selection
                if "Program" in selected_types and "Course" not in selected_types:
                    target_options = db_all_programs
                elif "Course" in selected_types and "Program" not in selected_types:
                    target_options = db_all_courses
                else:
                    target_options = sorted(list(set(db_all_programs + db_all_courses)))
                    
                selected_targets = st.multiselect("🎯 Filter by Name", target_options, key=f"target_{tab_key}")

        # Empty State Handling
        if df_schedules.empty:
            st.info("No faculty schedules available in this section yet.")
            return

        # Apply Filters to Dataframe
        filtered_df = df_schedules.copy()
        if selected_days:
            filtered_df = filtered_df[filtered_df['Day_of_Week'].isin(selected_days)]
        if selected_types:
            filtered_df = filtered_df[filtered_df['Booking_Scope'].isin(selected_types)]
        if selected_targets:
            filtered_df = filtered_df[filtered_df['Scope_Value'].isin(selected_targets)]

        if filtered_df.empty:
            st.warning("⚠️ No schedules match your selected filters. Try clearing them.")
            return

        # 🚀 NEW: LOGIC TO SORT SLOTS CHRONOLOGICALLY 
        import pandas as pd
        day_mapping = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5, "Saturday": 6, "Sunday": 7}
        
        # Create hidden columns for sorting
        filtered_df['Day_Order'] = filtered_df['Day_of_Week'].map(day_mapping)
        # Convert time to a sortable format safely
        filtered_df['Time_Order'] = pd.to_datetime(filtered_df['Start_Time'], errors='coerce') 
        
        # Sort by Day first, then by Start Time, then drop the temporary columns
        filtered_df = filtered_df.sort_values(['Day_Order', 'Time_Order']).drop(columns=['Day_Order', 'Time_Order'])

        # Display Result Count
        st.write("")
        st.markdown(f"#### 📅 Available Schedules ({len(filtered_df)} slots found)")
        
        # Render Individual Cards
        for _, row in filtered_df.iterrows():
            with st.container(border=True):
                # Clean Layout
                col_fac, col_time = st.columns([1.5, 1])
                
                with col_fac:
                    st.markdown(f"### 👨‍🏫 {row['Faculty_Name']}")
                    st.caption(f"**Department:** {row['Faculty_Program'] if pd.notna(row['Faculty_Program']) and row['Faculty_Program'] != 'None' else 'General'}")
                    
                    # Target Scope Badge
                    scope_icon = "🎓" if row['Booking_Scope'] == "Program" else "📖"
                    st.info(f"{scope_icon} **Target Audience:** {row['Booking_Scope']} ➡️ **{row['Scope_Value']}**")
                    
                    if pd.notna(row.get('Courses_Taught')) and row['Courses_Taught']:
                        st.markdown(f"📚 **Courses Taught:** {row['Courses_Taught']}")
                
                with col_time:
                    # Highlight the Day and Time more prominently
                    st.markdown(f"#### 🗓️ {row['Day_of_Week']}")
                    st.markdown(f"🕒 **{row['Start_Time']} - {row['End_Time']}**")
                    st.markdown(f"📍 Venue: **{row['Venue']}**")
                    
                    if pd.notna(row['Meeting_Link']) and str(row['Meeting_Link']).strip() != "":
                        st.markdown(f"🔗 **[Join Online Meeting]({row['Meeting_Link']})**")

                # Exception Tracking (Cancellations & Reschedules)
                if not df_exceptions.empty:
                    this_card_exceptions = df_exceptions[df_exceptions['Schedule_ID'] == row['Schedule_ID']]
                    if not this_card_exceptions.empty:
                        st.divider() # Separate base info from exceptions
                        st.markdown("**🔔 Important Updates for this Slot:**")
                        
                        for _, exc in this_card_exceptions.iterrows():
                            if exc['Status'] == 'Cancelled':
                                date_obj = pd.to_datetime(exc['Exception_Date'])
                                st.error(f"🚫 **CANCELLED:** The session on **{date_obj.strftime('%d %b %Y')} ({date_obj.strftime('%A')})** has been cancelled.")
                                
                            elif exc['Status'] == 'Rescheduled':
                                new_date_obj = pd.to_datetime(exc['New_Date']) if pd.notnull(exc['New_Date']) else pd.to_datetime(exc['Exception_Date']) 
                                resch_line = f"🔄 **RESCHEDULED:** Moved to **{new_date_obj.strftime('%d %b %Y')} ({new_date_obj.strftime('%A')})** | 🕒 {exc['New_Start_Time']} - {exc['New_End_Time']} | 📍 {exc['New_Venue']}"
                                
                                if pd.notna(exc['New_Meeting_Link']) and str(exc['New_Meeting_Link']).strip() != "":
                                    resch_line += f" | 🔗 [Join Here]({exc['New_Meeting_Link']})"
                                st.warning(resch_line) 

    # --- 5. RENDER MAIN TABS ---
    tab1, tab2 = st.tabs(["🏫 My Program & Courses", "🌐 All Other Faculty Hours"])
    
    with tab1:
        render_tab_content(df_my_program, "tab1")
    with tab2:
        render_tab_content(df_other_programs, "tab2")

# ==========================================
# MAIN APP EXECUTION FLOW
# ==========================================
if not st.session_state.logged_in:
    login()
else:
    user = st.session_state.user_data
    
    # 🔄 AUTO-REFRESH LOGIC (Har 5 seconds)
    # Note: Only set on Student Portal
    if user['Role'].strip().lower() == 'student':
        st_autorefresh(interval=50000, limit=None, key="student_autorefresh")
    
    if st.session_state.show_welcome_toast:
        st.toast(f"Welcome back, {user['FullName']}!", icon="👋")
        st.session_state.show_welcome_toast = False

    # Top Profile Bar
    with st.container(border=True):
        # Adjust Colum for add refresh button
        col_prof1, col_prof2, col_prof3, col_prof4, col_prof5 = st.columns([3.5, 2, 2, 1.2, 1.2])
        role_icon = "👨‍🏫" if user['Role'].strip().lower() == 'faculty' else "👨‍🎓"
        
        with col_prof1:
            st.markdown(f"""
                <div style="padding-top: 5px;">
                    <span style="font-size: 1.3rem; font-weight: 600;">{role_icon} {user['FullName']}</span><br>
                    <span style="font-size: 0.85rem; color: #888888; text-transform: uppercase; letter-spacing: 1px;">
                        Logged in as {user['Role'].strip()}
                    </span>
                </div>
            """, unsafe_allow_html=True)
        with col_prof2:
            st.markdown(f"""
                <div style="padding-top: 5px;">
                    <span style="font-size: 0.8rem; color: #888888; text-transform: uppercase; letter-spacing: 1px;">ID Number</span><br>
                    <span style="font-size: 1.1rem; font-weight: 500;">🆔 {user['UserID']}</span>
                </div>
            """, unsafe_allow_html=True)
        with col_prof3:
            st.markdown(f"""
                <div style="padding-top: 5px;">
                    <span style="font-size: 0.8rem; color: #888888; text-transform: uppercase; letter-spacing: 1px;">Program</span><br>
                    <span style="font-size: 1.1rem; font-weight: 500;">📚 {user['Program']}</span>
                </div>
            """, unsafe_allow_html=True)
            
        # with col_prof4:
        #     st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
        #     # 🔄 MANUAL REFRESH BUTTON (For instant updates)
        #     if st.button("🔄 Refresh", use_container_width=True):
        #         st.rerun()
                
        with col_prof5:
            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
            if st.button("🚪 Logout", use_container_width=True):
                logout()

    st.write("") 

    # Route based on Role
    if user['Role'].strip().lower() == 'faculty':
        render_faculty_ui(user['UserID'], user['FullName'], user['Program'])
    elif user['Role'].strip().lower() == 'student':
        render_student_ui(user['UserID'], user['FullName'], user['Program'])
    else:
        st.error("⚠️ Unknown Role detected. Please contact IT support.")
