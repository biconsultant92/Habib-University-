import pandas as pd
import datetime
from db_connection import fetch_data

# ==========================================
# STUDENT BACKEND LOGICS & DATABASE QUERIES
# ==========================================

def get_student_dashboard_data(program, student_id):
    """
    Fetches all base schedules, exceptions, faculty courses, 
    and the specific student's enrolled courses for the UI.
    """
    
    # --- 1. FETCH BASE SCHEDULES ---
    # Commented out f.MEETING_DESCR from the query
    query_base = """
    SELECT f.Schedule_ID, f.Day_of_Week, f.Start_Time, f.End_Time, 
           u.FullName AS Faculty_Name, u.Program AS Faculty_Program, 
           f.Venue, f.Meeting_Link, f.Booking_Scope, f.Scope_Value
    FROM Faculty_Base_Schedule f
    JOIN Users u ON f.Faculty_ID = u.UserID
    WHERE f.Is_Active = 1
    ORDER BY f.Day_of_Week, f.Start_Time
    """
    df_base = fetch_data(query_base)

    # --- 2. FETCH EXCEPTIONS ---
    query_exceptions = """
    SELECT e.Schedule_ID, e.Exception_Date, e.New_Date, e.Status, e.New_Start_Time, e.New_End_Time, e.New_Venue, e.New_Meeting_Link,
           u.FullName AS Faculty_Name, f.Day_of_Week, f.End_Time AS Base_End_Time
    FROM Schedule_Exceptions e
    JOIN Faculty_Base_Schedule f ON e.Schedule_ID = f.Schedule_ID
    JOIN Users u ON f.Faculty_ID = u.UserID
    WHERE e.Exception_Date >= CAST(GETDATE() AS DATE) 
       OR e.New_Date >= CAST(GETDATE() AS DATE)
    ORDER BY e.Exception_Date
    """
    df_exceptions = fetch_data(query_exceptions)

    # --- 3. AUTO-EXPIRE EXCEPTIONS ---
    if not df_exceptions.empty:
        now = datetime.datetime.now()
        valid_indices = []
        for idx, row in df_exceptions.iterrows():
            try:
                if row['Status'] == 'Rescheduled' and pd.notnull(row['New_Date']):
                    exc_date = pd.to_datetime(row['New_Date']).date()
                else:
                    exc_date = pd.to_datetime(row['Exception_Date']).date()
                
                end_time_val = row['New_End_Time'] if row['Status'] == 'Rescheduled' and pd.notnull(row['New_End_Time']) else row['Base_End_Time']
                
                if isinstance(end_time_val, str):
                    end_time_obj = pd.to_datetime(end_time_val).time()
                elif isinstance(end_time_val, datetime.time):
                    end_time_obj = end_time_val
                else:
                    end_time_obj = datetime.time(23, 59)
                
                exc_full_datetime = datetime.datetime.combine(exc_date, end_time_obj)
                
                if exc_full_datetime >= now:
                    valid_indices.append(idx)
            except Exception as e:
                valid_indices.append(idx)
        
        df_exceptions = df_exceptions.loc[valid_indices].copy()

    # --- 4. FETCH FACULTY COURSES ---
    query_courses = """
    SELECT DISTINCT INSTRUCTOR_NAME, DESCR 
    FROM PSCS_Course_2611_term
    """
    df_courses = fetch_data(query_courses)

    if not df_courses.empty:
        df_courses_grouped = df_courses.groupby('INSTRUCTOR_NAME')['DESCR'].apply(lambda x: ', '.join(x)).reset_index()
        df_courses_grouped.rename(columns={'DESCR': 'Courses_Taught'}, inplace=True)
        
        if not df_base.empty:
            df_base = pd.merge(df_base, df_courses_grouped, how='left', left_on='Faculty_Name', right_on='INSTRUCTOR_NAME')
            df_base['Courses_Taught'] = df_base['Courses_Taught'].fillna('N/A')
    else:
        if not df_base.empty:
            df_base['Courses_Taught'] = 'N/A'

    # --- 5. CLEAN AND FORMAT DATA ---
    if not df_base.empty:
        df_base['Start_Time'] = pd.to_datetime(df_base['Start_Time'].astype(str)).dt.strftime('%I:%M %p')
        df_base['End_Time'] = pd.to_datetime(df_base['End_Time'].astype(str)).dt.strftime('%I:%M %p')
        # COMMENTED OUT MEETING_DESCR CLEANUP
        # df_base['MEETING_DESCR'] = df_base['MEETING_DESCR'].fillna("Regular Semester")

    if not df_exceptions.empty:
        df_exceptions['New_Start_Time'] = pd.to_datetime(df_exceptions['New_Start_Time'].dropna().astype(str)).dt.strftime('%I:%M %p')
        df_exceptions['New_End_Time'] = pd.to_datetime(df_exceptions['New_End_Time'].dropna().astype(str)).dt.strftime('%I:%M %p')

    # --- 6. SEPARATING DATA FOR TABS ---
    df_my_program = df_base[df_base['Faculty_Program'] == program].copy() if not df_base.empty else pd.DataFrame()
    df_other_programs = df_base[df_base['Faculty_Program'] != program].copy() if not df_base.empty else pd.DataFrame()

    # --- 7. FETCH STUDENT ENROLLED COURSES ---
    try:
        # Aapke actual database table (PSCS_Course_2611_term) ke hisaab se query
        query_student_courses = """
        SELECT DISTINCT DESCR AS Course_Name 
        FROM PSCS_Course_2611_term 
        WHERE EMPLID = ?
        """
        # Note: EMPLID text format mein ho sakta hai, isliye student_id ko str() mein convert kar rahe hain
        df_student_courses = fetch_data(query_student_courses, (str(student_id),))
    except Exception as e:
        # Agar koi issue aaye toh empty dataframe return karein
        df_student_courses = pd.DataFrame(columns=['Course_Name'])

    return df_my_program, df_other_programs, df_exceptions, df_student_courses

    # Returned the newly created dataframe alongside the existing ones
    return df_my_program, df_other_programs, df_exceptions, df_student_courses