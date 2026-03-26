import pandas as pd
import datetime
from db_connection import fetch_data, execute_query
from availability_logic import calculate_availability

# ==========================================
# FACULTY BACKEND LOGICS & DATABASE QUERIES
# ==========================================

def get_time_slots():
    """Generates a list of time slots from 8 AM to 6 PM."""
    slots = []
    for h in range(8, 20): 
        for m in [0, 15, 30, 45]: 
            t = datetime.time(h, m)
            slots.append(t.strftime("%I:%M %p")) 
    return slots

def get_faculty_venues(full_name):
    """Fetches faculty-specific pod and room from the database."""
    profile_query = "SELECT FacultyPod, OfficeRoomNo FROM FacultyProfiles WHERE FacultyName = ?"
    df_profile = fetch_data(profile_query, (full_name,))
    
    base_venue_options = [] 
    if not df_profile.empty:
        pod = str(df_profile.iloc[0]['FacultyPod']) if pd.notna(df_profile.iloc[0]['FacultyPod']) else ""
        room = str(df_profile.iloc[0]['OfficeRoomNo']) if pd.notna(df_profile.iloc[0]['OfficeRoomNo']) else ""
        
        if pod and room and pod != "None" and room != "None":
            base_venue_options.append(f"{pod} - {room}")
        if pod and pod != "None" and pod not in base_venue_options:
            base_venue_options.append(pod)
        if room and room != "None" and room not in base_venue_options:
            base_venue_options.append(room)
            
    base_venue_options.extend(["Online", "Other"])
    return base_venue_options

def get_faculty_courses(user_id):
    """Fetches courses assigned to the faculty."""
    course_query = "SELECT DISTINCT CRSE_ID, DESCR FROM PSCS_Course_2611_term WHERE INSTR_EMPLID = ?"
    df_courses = fetch_data(course_query, (user_id,))
    if not df_courses.empty:
        return dict(zip(df_courses['DESCR'], df_courses['CRSE_ID']))
    return {}

def fetch_student_schedules_for_booking(booking_scope, scope_value, program, term_condition):
    """
    Fetches the class schedules of students belonging to the target audience.
    If scope is 'Program', it fetches all students in that program.
    If scope is 'Course', it fetches only students enrolled in that specific course(s).
    """
    if booking_scope == "Program":
        # Clean program string (e.g., 'BS CS' becomes 'CS') for broader matching
        safe_program = str(program) if pd.notna(program) and program else ""
        core_prog = safe_program.replace("BS ", "").replace("BS-", "").strip()
        
        query = f"""
        SELECT * FROM PSCS_Course_2611_term 
        WHERE EMPLID IN (
            SELECT UserID FROM Users 
            WHERE Program LIKE ? OR Program LIKE ? OR Program = ?
        )
        {term_condition}
        """
        params = (f"%{safe_program}%", f"%{core_prog}%", core_prog)
        
    else:
        # Check if scope_value is a list (from st.multiselect) or a single string
        if isinstance(scope_value, list) and len(scope_value) > 0:
            # Create dynamic placeholders based on the number of selected courses
            placeholders = ', '.join(['?'] * len(scope_value))
            params = tuple(scope_value) 
        else:
            # Fallback for a single string selection
            placeholders = '?'
            params = (scope_value,)
            
        # FIX: Use DESCR instead of CRSE_ID to match the exact course name
        query = f"""
        SELECT * FROM PSCS_Course_2611_term 
        WHERE EMPLID IN (
            SELECT EMPLID FROM PSCS_Course_2611_term WHERE DESCR IN ({placeholders})
        )
        {term_condition}
        """
        
    return fetch_data(query, params)

import datetime

def generate_alternative_suggestions(df_schedule, day_of_week, start_time_obj, end_time_obj, selected_term, percent, booking_frequency="Whole Semester", specific_date=None, num_suggestions=3, **kwargs):
    """Calculates and returns top alternative time slots with higher availability."""
    start_dt = datetime.datetime.combine(datetime.date.today(), start_time_obj)
    end_dt = datetime.datetime.combine(datetime.date.today(), end_time_obj)
    duration_min = int((end_dt - start_dt).total_seconds() / 60)

    suggestions = []
    if duration_min > 0:
        test_time = datetime.datetime.combine(datetime.date.today(), datetime.time(8, 30))
        end_limit = datetime.datetime.combine(datetime.date.today(), datetime.time(18, 0))
        
        while test_time + datetime.timedelta(minutes=duration_min) <= end_limit:
            t_start = test_time.time()
            t_end = (test_time + datetime.timedelta(minutes=duration_min)).time()
            
            if t_start == start_time_obj and t_end == end_time_obj:
                test_time += datetime.timedelta(minutes=30)
                continue
                
            try:
                
                s_count, s_percent = calculate_availability(
                    df_schedule, day_of_week, t_start, t_end, selected_term
                )
                
                if s_percent > percent:
                    suggestions.append({
                        'start_str': t_start.strftime("%I:%M %p"),
                        'end_str': t_end.strftime("%I:%M %p"),
                        'count': s_count,
                        'percent': s_percent
                    })
            except Exception:
                pass 
                
            test_time += datetime.timedelta(minutes=30) 
    
    suggestions.sort(key=lambda x: x['percent'], reverse=True)
    
    # 💡 YAHAN FIX KIYA HAI: '3' ki jagah 'num_suggestions' laga diya hai
    return suggestions[:num_suggestions]

def save_base_schedule(user_id, booking_scope, scope_value, day_of_week, start_time_obj, end_time_obj, final_venue, meeting_link, db_term, booking_frequency, specific_dates=None):
    """Inserts a new base schedule into the database."""
    
    insert_query = """
    INSERT INTO Faculty_Base_Schedule 
    (STRM, Faculty_ID, Booking_Scope, Scope_Value, Day_of_Week, Start_Time, End_Time, Venue, Meeting_Link, MEETING_DESCR, Booking_Frequency, Specific_Dates)
    VALUES (2611, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # Ensure scope_value is a string
    if isinstance(scope_value, list):
        scope_value = ", ".join([str(val) for val in scope_value])
        
    # 🛠️ FIX: Ensure specific_dates is a string before sending to SQL Server
    if isinstance(specific_dates, list):
        specific_dates = ", ".join([str(d) for d in specific_dates])
        
    return execute_query(insert_query, (
        user_id, 
        booking_scope, 
        scope_value, 
        day_of_week, 
        start_time_obj, 
        end_time_obj, 
        final_venue, 
        meeting_link, 
        db_term, 
        booking_frequency, 
        specific_dates
    ))
def get_my_base_schedules(user_id):
    """Fetches the active base schedules for a specific faculty member."""
    my_schedule_query = """
    SELECT Schedule_ID, Day_of_Week, MEETING_DESCR, Start_Time, End_Time, Booking_Scope, Scope_Value, Venue, Meeting_Link
    FROM Faculty_Base_Schedule 
    WHERE Faculty_ID = ? AND Is_Active = 1
    ORDER BY Day_of_Week, Start_Time
    """
    df_my_schedule = fetch_data(my_schedule_query, (user_id,))
    
    if not df_my_schedule.empty:
        df_my_schedule['Start_Time'] = pd.to_datetime(df_my_schedule['Start_Time'].astype(str)).dt.strftime('%I:%M %p')
        df_my_schedule['End_Time'] = pd.to_datetime(df_my_schedule['End_Time'].astype(str)).dt.strftime('%I:%M %p')
        # Fill empty MEETING_DESCR with "Regular Schedule" to keep UI consistent
        df_my_schedule['MEETING_DESCR'] = df_my_schedule['MEETING_DESCR'].fillna("Regular Schedule")
    
    return df_my_schedule

def save_single_date_exception(schedule_id, exception_date, status, new_date, new_start, new_end, new_venue, new_link):
    """Saves a cancellation or reschedule for a specific single date."""
    exception_query = """
    INSERT INTO Schedule_Exceptions 
    (Schedule_ID, Exception_Date, Status, New_Date, New_Start_Time, New_End_Time, New_Venue, New_Meeting_Link)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_query(exception_query, (schedule_id, exception_date, status, new_date, new_start, new_end, new_venue, new_link))

def cancel_permanent_schedule(schedule_id):
    """Marks a base schedule as inactive permanently."""
    return execute_query("UPDATE Faculty_Base_Schedule SET Is_Active = 0 WHERE Schedule_ID = ?", (schedule_id,))

def update_permanent_schedule(new_day, start_time, end_time, venue, link, schedule_id):
    """Updates the time, day, or venue of a base schedule permanently."""
    update_query = """
    UPDATE Faculty_Base_Schedule 
    SET Day_of_Week = ?, Start_Time = ?, End_Time = ?, Venue = ?, Meeting_Link = ?
    WHERE Schedule_ID = ?
    """
    return execute_query(update_query, (new_day, start_time, end_time, venue, link, schedule_id))