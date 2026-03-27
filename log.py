import streamlit as st
import uuid
import datetime

from db_connection import execute_query 

def log_action(description, module_accessed="System", reference_id=None, is_login=False, is_logout=False):
    """
    Yeh function naye professional database structure ke hisaab se logs save karta hai.
    Action_Type ki jagah is_login aur is_logout use hota hai taake time theek se track ho.
    """
    # 1. Session ID (if session id is not available then create)
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())
    session_id = st.session_state['session_id']

    # 2. Login Time Tracking (Session State mein save rakhne ke liye)
    if is_login:
        st.session_state['login_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    login_time = st.session_state.get('login_time', None)

    # 3. User Details (Auto Session state)
    user_id = None
    user_name = "Guest"
    user_email = "Unknown"
    user_role = "Unknown"

    if 'user_data' in st.session_state and st.session_state.user_data is not None:
        user = st.session_state.user_data
        user_id = user.get('UserID')
        user_name = user.get('FullName', 'Guest')
        user_email = user.get('Email', 'Unknown')
        user_role = user.get('Role', 'Unknown')

    # 4. IP Address Fetching (Network or Local machine ka IP)
    try:
        headers = st.context.headers
        ip_address = headers.get("X-Forwarded-For", headers.get("Host", "Unknown IP"))
    except Exception:
        ip_address = "Unknown IP"

    # 5. Database Smart Query Execution
    try:
        if is_logout:
            # 🔴 LOGOUT: Us session ki sari rows mein Logout_Time update kar do
            update_query = """
                UPDATE [faculty_student].[dbo].[System_Logs]
                SET [Logout_Time] = GETDATE()
                WHERE [Session_ID] = ?
            """
            execute_query(update_query, (session_id,))
            
            # Logout ki entry alag se bhi daal dete hain
            insert_query = """
                INSERT INTO [faculty_student].[dbo].[System_Logs] 
                ([Session_ID], [UserID], [User_Email], [User_Role], [IP_Address], 
                 [Module_Accessed], [Activity_Description], [Login_Time], [Logout_Time])
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """
            params = (session_id, user_id, user_email, user_role, ip_address, module_accessed, description, login_time)
            execute_query(insert_query, params)
            
            print(f"✅ SUCCESS: LOGOUT Recorded for {user_name} ({user_email})")
            
            # Clear session tracking for logs after logout
            if 'session_id' in st.session_state:
                del st.session_state['session_id']
            if 'login_time' in st.session_state:
                del st.session_state['login_time']

        else:
            # 🟢 LOGIN YA OTHER ACTIVITY: Sirf nayi row Insert hogi
            insert_query = """
                INSERT INTO [faculty_student].[dbo].[System_Logs] 
                ([Session_ID], [UserID], [User_Email], [User_Role], [IP_Address], 
                 [Module_Accessed], [Activity_Description], [Reference_ID], [Login_Time])
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                session_id, user_id, user_email, user_role, ip_address, 
                module_accessed, description, reference_id, login_time
            )
            execute_query(insert_query, params)
            
            print(f"✅ SUCCESS: Log Saved -> {description} by {user_name}")

    except Exception as e:
        # If Logging fail system don't crash that why use print
        print(f"❌ Log Error: {e}")