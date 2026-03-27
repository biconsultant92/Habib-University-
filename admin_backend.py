import pandas as pd
from db_connection import fetch_data, execute_query

# ==========================================
# ADMIN BACKEND LOGICS & DATABASE QUERIES
# ==========================================

def get_dashboard_stats():
    """
    Fetches quick statistics for the Admin Dashboard.
    Returns total active schedules, exceptions, total registered faculty, and students.
    """
    stats = {
        'total_active_schedules': 0,
        'total_exceptions': 0,
        'total_faculty': 0,
        'total_students': 0
    }
    
    try:
        # 1. Get count of active base schedules
        sched_query = "SELECT COUNT(*) as count FROM Faculty_Base_Schedule WHERE Is_Active = 1"
        df_sched = fetch_data(sched_query)
        if not df_sched.empty:
            stats['total_active_schedules'] = df_sched.iloc[0]['count']
            
        # 2. Get count of all exceptions (reschedules/cancellations)
        exc_query = "SELECT COUNT(*) as count FROM Schedule_Exceptions"
        df_exc = fetch_data(exc_query)
        if not df_exc.empty:
            stats['total_exceptions'] = df_exc.iloc[0]['count']
            
        # 3. Get count of total registered faculty
        fac_query = "SELECT COUNT(*) as count FROM Users WHERE Role = 'Faculty'"
        df_fac = fetch_data(fac_query)
        if not df_fac.empty:
            stats['total_faculty'] = df_fac.iloc[0]['count']
            
        # 4. Get count of total registered students
        stu_query = "SELECT COUNT(*) as count FROM Users WHERE Role = 'Student'"
        df_stu = fetch_data(stu_query)
        if not df_stu.empty:
            stats['total_students'] = df_stu.iloc[0]['count']
            
    except Exception as e:
        print(f"Error fetching admin stats: {e}")
        
    return stats

def get_all_faculty_schedules():
    """
    Fetches all active schedules for all faculty members across the university.
    Joins with the Users table to retrieve the full name and program of the faculty.
    """
    query = """
    SELECT 
        u.FullName AS Faculty_Name,
        u.Program AS Department,
        f.Day_of_Week,
        f.Start_Time,
        f.End_Time,
        f.Booking_Scope,
        f.Scope_Value,
        f.Venue,
        f.Meeting_Link,
        f.MEETING_DESCR,
        f.Booking_Frequency,
        f.Specific_Dates,
        f.Availability_Percent
    FROM Faculty_Base_Schedule f
    JOIN Users u ON f.Faculty_ID = u.UserID
    WHERE f.Is_Active = 1
    ORDER BY f.Day_of_Week, f.Start_Time
    """
    
    df_all_schedules = fetch_data(query)
    
    if not df_all_schedules.empty:
        # Warning fix: format='mixed' helps pandas process times cleanly
        df_all_schedules['Start_Time'] = pd.to_datetime(df_all_schedules['Start_Time'].astype(str), format='mixed', errors='coerce').dt.strftime('%I:%M %p')
        df_all_schedules['End_Time'] = pd.to_datetime(df_all_schedules['End_Time'].astype(str), format='mixed', errors='coerce').dt.strftime('%I:%M %p')
        
        df_all_schedules['MEETING_DESCR'] = df_all_schedules['MEETING_DESCR'].fillna("Regular Schedule")
        df_all_schedules['Specific_Dates'] = df_all_schedules['Specific_Dates'].fillna("-")
        df_all_schedules['Availability_Percent'] = df_all_schedules['Availability_Percent'].fillna(0.0)
        
    return df_all_schedules

def get_all_exceptions():
    """
    Fetches all modified schedules (Cancellations and Reschedules) across the university.
    """
    query = """
    SELECT 
        u.FullName AS Faculty_Name,
        f.Day_of_Week AS Original_Day,
        e.Exception_Date AS Target_Date,
        e.Status,
        e.New_Date,
        e.New_Start_Time,
        e.New_End_Time,
        e.New_Venue,
        e.New_Availability_Percent
    FROM Schedule_Exceptions e
    JOIN Faculty_Base_Schedule f ON e.Schedule_ID = f.Schedule_ID
    JOIN Users u ON f.Faculty_ID = u.UserID
    ORDER BY e.Exception_Date DESC
    """
    
    df_exceptions = fetch_data(query)
    
    if not df_exceptions.empty:
        # 🌟 BUG FIX: Convert Target_Date and New_Date into pure strings FIRST, then fillna('-')
        df_exceptions['Target_Date'] = pd.to_datetime(df_exceptions['Target_Date'], errors='coerce').dt.strftime('%d %b %Y')
        df_exceptions['New_Date'] = pd.to_datetime(df_exceptions['New_Date'], errors='coerce').dt.strftime('%d %b %Y').fillna('-')
        
        df_exceptions['New_Start_Time'] = pd.to_datetime(df_exceptions['New_Start_Time'].astype(str), format='mixed', errors='coerce').dt.strftime('%I:%M %p').fillna('-')
        df_exceptions['New_End_Time'] = pd.to_datetime(df_exceptions['New_End_Time'].astype(str), format='mixed', errors='coerce').dt.strftime('%I:%M %p').fillna('-')
        
        df_exceptions['New_Venue'] = df_exceptions['New_Venue'].fillna('-')
        df_exceptions['New_Availability_Percent'] = df_exceptions['New_Availability_Percent'].fillna(0.0)
        
    return df_exceptions

def get_filter_options():
    """
    Retrieves unique lists of faculty names and programs to populate Admin UI filter dropdowns.
    """
    options = {
        'departments': [],
        'faculty_names': []
    }
    
    try:
        # Fetch unique active departments/programs
        prog_query = "SELECT DISTINCT Program FROM Users WHERE Role = 'Faculty' AND Program IS NOT NULL"
        df_prog = fetch_data(prog_query)
        if not df_prog.empty:
            options['departments'] = sorted(df_prog['Program'].dropna().unique().tolist())
            
        # Fetch unique faculty names
        fac_query = "SELECT DISTINCT FullName FROM Users WHERE Role = 'Faculty' AND FullName IS NOT NULL"
        df_fac = fetch_data(fac_query)
        if not df_fac.empty:
            options['faculty_names'] = sorted(df_fac['FullName'].dropna().unique().tolist())
            
    except Exception as e:
        print(f"Error fetching filter options: {e}")
        
    return options