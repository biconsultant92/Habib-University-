import pandas as pd
from datetime import datetime, timedelta, time
import numpy as np

def calculate_availability(df_schedule, target_day, fac_start_time, fac_end_time, selected_term="All Periods", booking_frequency="Whole Semester", specific_dates=None):
    """
    Calculates the percentage of students available during a specific faculty slot.
    Condition: A student is considered 'available' if they have at least a continuous 
    30-minute free window within the requested faculty time slot.
    
    NEW FEATURES:
    - Multi-Course: The df_schedule inherently handles multiple courses. Using .unique() 
      ensures students taking multiple selected courses are only counted once.
    - Specific Dates: Allows filtering availability for specific dates rather than the whole semester.
    """
    
    # ==========================================
    # 1. GET TOTAL STUDENTS (Before Filtering)
    # ==========================================
    total_students = df_schedule['EMPLID'].dropna().unique()
    total_count = len(total_students)
    
    if total_count == 0:
        return 0, 0.0

    # ==========================================
    # 2. DATA SANITIZATION & DAY MATCHING
    # ==========================================
    day_col = 'Day_of_Week' 
    if day_col not in df_schedule.columns:
        possible_cols = ['Clean_Day', 'Day', 'CLASS_MTG_DAYS']
        for col in possible_cols:
            if col in df_schedule.columns:
                day_col = col
                break
                
    if day_col not in df_schedule.columns:
        print("Error: Day column not found in the schedule dataframe.")
        return 0, 0.0

    df_schedule[day_col] = df_schedule[day_col].astype(str).str.strip().str.lower()
    target_day = target_day.strip().lower()
    
    # ==========================================
    # 3. TERM PERIOD FILTERING (CURRENTLY COMMENTED OUT)
    # ==========================================
    
    # if 'MEETING_DESCR' in df_schedule.columns:
    #     if selected_term == "All Periods" or selected_term == "NULL":
    #         df_term = df_schedule.copy()
    #     elif "Makeup" in str(selected_term):
    #         # FIX: For makeup sessions, we must check for conflicts against the student's 
    #         # REGULAR classes. If we filter by 'Makeup Session', we accidentally delete their schedule!
    #         df_term = df_schedule[
    #             df_schedule['MEETING_DESCR'].isna() | 
    #             (df_schedule['MEETING_DESCR'].str.strip() == '') | 
    #             (df_schedule['MEETING_DESCR'].str.contains('Regular', case=False, na=False)) |
    #             (df_schedule['MEETING_DESCR'].str.contains('Pre Ramazan', case=False, na=False)) 
    #         ].copy()
    #     else:
    #         # For specific terms like 'Ramazan Timing'
    #         df_term = df_schedule[df_schedule['MEETING_DESCR'] == selected_term].copy()
    #         
    #     # SAFETY FALLBACK:
    #     if df_term.empty:
    #         df_term = df_schedule.copy()
    # else:
    #     df_term = df_schedule.copy()

    # Default fallback to original behavior (no term filtering)
    df_term = df_schedule.copy()

    # Filter the schedule for the specific target day (e.g., 'wednesday')
    df_day = df_term[df_term[day_col] == target_day].copy()

    # ==========================================
    # 3.5. SPECIFIC DATES vs WHOLE SEMESTER LOGIC
    # ==========================================
    # If the faculty chose "Specific Date(s)", we check if those specific dates have extra conflicts.
    # Standard university schedules are weekly, so filtering by 'target_day' (above) usually covers it.
    # However, if the database has a specific date column for exceptions (like exams, one-off events),
    # we filter the data here to check availability only for the selected dates.
    
    if booking_frequency == "Specific Date(s)" and specific_dates:
        # Check if the dataframe contains a date-specific column
        date_col = next((col for col in ['Class_Date', 'Date', 'Specific_Date'] if col in df_day.columns), None)
        
        if date_col:
            # Convert dates to string to ensure matching works properly
            df_day[date_col] = df_day[date_col].astype(str)
            # Keep regular weekly schedules (where date might be NaN/None) OR the specific dates requested
            df_day = df_day[df_day[date_col].isna() | df_day[date_col].isin(specific_dates)].copy()

    # ==========================================
    # 4. PREPARE TIME VARIABLES
    # ==========================================
    available_count = 0
    today = datetime.today().date()
    fac_start = datetime.combine(today, fac_start_time)
    fac_end = datetime.combine(today, fac_end_time)
    
    total_fac_duration = fac_end - fac_start
    required_gap = min(timedelta(minutes=30), total_fac_duration)

    def parse_time(t):
        if pd.isna(t):
            return None
        if isinstance(t, time):
            return t
        try:
            return pd.to_datetime(str(t)).time()
        except Exception:
            return None

    # ==========================================
    # 5. AVAILABILITY CALCULATION LOOP
    # ==========================================
    for student_id in total_students:
        student_classes = df_day[df_day['EMPLID'] == student_id]
        
        if student_classes.empty:
            available_count += 1
            continue
            
        student_classes = student_classes.dropna(subset=['Start_Time', 'End_Time']).copy()
        student_classes['Start_Time_Parsed'] = student_classes['Start_Time'].apply(parse_time)
        student_classes['End_Time_Parsed'] = student_classes['End_Time'].apply(parse_time)
        student_classes = student_classes.dropna(subset=['Start_Time_Parsed', 'End_Time_Parsed'])
        
        student_classes = student_classes.sort_values(by='Start_Time_Parsed')
        
        is_available = False
        current_check_time = fac_start
        
        for index, row in student_classes.iterrows():
            class_start = datetime.combine(today, row['Start_Time_Parsed'])
            class_end = datetime.combine(today, row['End_Time_Parsed'])
            
            if class_end <= current_check_time:
                continue
                
            if class_start > current_check_time:
                gap = class_start - current_check_time
                if gap >= required_gap:
                    is_available = True
                    break
                    
            if class_end > current_check_time:
                current_check_time = class_end
                
            if current_check_time >= fac_end:
                break
                
        if not is_available and current_check_time < fac_end:
            final_gap = fac_end - current_check_time
            if final_gap >= required_gap:
                is_available = True
                
        if is_available:
            available_count += 1

    percentage = (available_count / total_count) * 100 if total_count > 0 else 0.0
    return available_count, round(percentage, 2)