import streamlit as st
import os
import requests

def apply_custom_theme():
    if 'theme' not in st.session_state:
        st.session_state.theme = 'dark'
        
    if st.session_state.theme == 'dark':
        css_vars = """
        :root {
            --bg-color: #0B1120;
            --surface-color: rgba(30, 41, 59, 0.6);
            --surface-color-solid: #1E293B;
            --accent-color: #3B82F6; 
            --accent-hover: #60A5FA;
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
            --glow-color: rgba(59, 130, 246, 0.15);
        }
        """
    else:
        css_vars = """
        :root {
            --bg-color: #F8FAFC;
            --surface-color: rgba(255, 255, 255, 0.7);
            --surface-color-solid: #FFFFFF;
            --accent-color: #2563EB; 
            --accent-hover: #1D4ED8;
            --border-color: rgba(15, 23, 42, 0.08);
            --text-main: #0F172A;
            --text-muted: #64748B;
            --glow-color: rgba(37, 99, 235, 0.1);
        }
        """

    custom_css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

    {css_vars}

    /* Base Streamlit App Background & Typography */
    html, body, [class*="css"] {{
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}
    
    .stApp {{
        background-color: var(--bg-color) !important;
        background-image: 
            radial-gradient(at 0% 0%, var(--glow-color) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(192, 132, 252, 0.1) 0px, transparent 50%) !important;
        background-attachment: fixed !important;
    }}

    /* Sidebar UI */
    [data-testid="stSidebar"] {{
        background-color: var(--surface-color) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--border-color) !important;
    }}

    /* Always-visible scrollbar in the sidebar */
    [data-testid="stSidebar"] > div:first-child {{
        overflow-y: scroll !important;
        scrollbar-width: thin !important;          /* Firefox */
        scrollbar-color: #334155 transparent !important; /* Firefox thumb + track */
    }}

    /* Webkit (Chrome / Edge) */
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar {{
        width: 6px !important;
    }}
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-track {{
        background: transparent !important;
    }}
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb {{
        background-color: #334155 !important;
        border-radius: 3px !important;
    }}
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb:hover {{
        background-color: #475569 !important;
    }}
    
    [data-testid="stSidebarNav"] span {{
        color: var(--text-main) !important;
    }}

    [data-testid="stSidebarNav"] a {{
        border-radius: 6px !important;
        transition: background-color 0.2s ease, transform 0.1s ease !important;
    }}

    [data-testid="stSidebarNav"] a:hover {{
        background-color: var(--surface-color) !important;
    }}

    /* Top Header */
    header[data-testid="stHeader"] {{
        background-color: var(--bg-color) !important;
        border-bottom: 1px solid var(--border-color) !important;
    }}

    /* Gradients & Typography */
    .gradient-text {{
        background: linear-gradient(90deg, #60A5FA, #C084FC, #F472B6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
        font-weight: 800;
        font-size: 2.5rem;
    }}
    
    .hero-title {{
        text-align: center;
        color: var(--text-main);
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }}
    
    .hero-subtitle {{
        text-align: center;
        color: var(--text-muted);
        font-size: 1.15rem;
        max-width: 600px;
        margin: 0 auto 3rem auto;
        line-height: 1.6;
        font-weight: 300;
    }}

    /* Step Cards for Instructions */
    .step-card {{
        background: var(--surface-color);
        backdrop-filter: blur(12px);
        border: 1px solid var(--border-color);
        border-radius: 20px;
        padding: 2rem;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        text-align: left;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        overflow: hidden;
        z-index: 1;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }}
    
    .step-card::before {{
        content: "";
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 0%;
        background: linear-gradient(180deg, transparent, var(--step-color));
        opacity: 0.15;
        z-index: -1;
        transition: height 0.5s cubic-bezier(0.165, 0.84, 0.44, 1);
    }}
    
    .step-card:hover::before {{
        height: 100%;
    }}
    
    .step-card:hover {{
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 40px -10px var(--step-color);
        border-color: var(--step-color);
    }}
    
    .step-number {{
        font-size: 3.5rem; 
        font-weight: 900; 
        margin-bottom: 0.75rem; 
        opacity: 0.85; 
        line-height: 1;
        transition: color 0.4s ease;
    }}
    
    .step-title {{
        color: var(--text-main);
        font-weight: 700;
        font-size: 1.3rem;
        margin-bottom: 0.5rem;
        transition: color 0.4s ease;
    }}
    
    .step-desc {{
        color: var(--text-muted);
        font-size: 0.95rem;
        transition: color 0.4s ease;
    }}
    
    .step-card:hover .step-number,
    .step-card:hover .step-title,
    .step-card:hover .step-desc {{
        color: #ffffff !important;
    }}
    
    .feature-desc {{
        color: var(--text-muted);
        font-size: 0.9rem;
        line-height: 1.4;
    }}

    /* Timeline Cards for Home Page */
    .timeline-card {{
        position: relative;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 24px;
        padding: 2.5rem 2rem;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        backdrop-filter: blur(12px);
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
        height: 100%;
    }}
    
    .timeline-card:hover {{
        transform: translateY(-8px);
        border-color: var(--timeline-color);
        box-shadow: 0 10px 40px -10px var(--timeline-color);
    }}
    
    .timeline-bg-num {{
        position: absolute;
        right: -10px;
        bottom: -20px;
        font-size: 8rem;
        font-weight: 900;
        color: var(--timeline-color);
        opacity: 0.05;
        line-height: 1;
        pointer-events: none;
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 0;
    }}
    
    .timeline-card:hover .timeline-bg-num {{
        transform: scale(1.15) rotate(-5deg);
        opacity: 0.15;
    }}
    
    .timeline-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 55px;
        height: 55px;
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.03);
        color: var(--timeline-color);
        font-size: 1.8rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255,255,255,0.05);
        z-index: 1;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }}
    
    .timeline-title {{
        font-size: 1.4rem;
        font-weight: 800;
        color: var(--text-main);
        margin-bottom: 0.75rem;
        z-index: 1;
    }}
    
    .timeline-desc {{
        color: var(--text-muted);
        font-size: 1rem;
        line-height: 1.6;
        z-index: 1;
        flex-grow: 1;
    }}

    /* Flip Cards */
    .flip-card {{
        background-color: transparent;
        height: 210px;
        perspective: 1000px;
        margin-bottom: 1rem;
    }}
    
    .flip-card-inner {{
        position: relative;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        transform-style: preserve-3d;
    }}
    
    .flip-card:hover .flip-card-inner {{
        transform: rotateY(180deg);
    }}
    
    .flip-card-front, .flip-card-back {{
        position: absolute;
        width: 100%;
        height: 100%;
        backface-visibility: hidden;
        border-radius: 12px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.5rem;
    }}
    
    .flip-card-front {{
        background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 100%), var(--surface-color);
        border: 1px solid var(--border-color);
        box-shadow: 0 8px 16px -4px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }}
    
    .flip-card-back {{
        background-color: var(--surface-color);
        transform: rotateY(180deg);
        box-shadow: 0 15px 25px -5px rgba(0, 0, 0, 0.2);
    }}

    /* Mock Chat Input Wrapper */
    .mock-chat-wrapper {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 24px;
        padding: 0.5rem 1rem;
        display: flex;
        align-items: center;
        margin-top: 4rem;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }}
    
    .mock-chat-input {{
        flex-grow: 1;
        background: transparent;
        border: none;
        color: var(--text-main);
        font-size: 1rem;
        padding: 0.5rem;
        outline: none;
    }}

    /* Sidebar Stats Box */
    .sidebar-stats-box {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
    }}
    
    .stats-row {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
    }}
    
    .stats-label {{
        color: var(--text-muted);
    }}
    
    .stats-value {{
        color: var(--text-main);
        font-weight: 500;
    }}

    /* Sidebar User Profile - pinned to bottom via flex */
    .sidebar-user-profile {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.75rem;
        display: flex;
        align-items: center;
        margin-top: auto;
        width: 100%;
    }}
    
    .user-avatar {{
        width: 32px;
        height: 32px;
        background-color: #3B82F6;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        margin-right: 0.75rem;
    }}
    
    .user-info {{
        display: flex;
        flex-direction: column;
    }}
    
    .user-name {{
        color: var(--text-main);
        font-weight: 600;
        font-size: 0.9rem;
    }}
    
    .user-role {{
        color: var(--text-muted);
        font-size: 0.75rem;
    }}

    /* Hide default metric styling we don't want */
    [data-testid="stMetricValue"] {{
        color: var(--text-main) !important;
    }}
    
    /* End Session Button global styling fallback */
    [data-testid="stSidebar"] button[kind="primary"] {{
        background-color: #DC2626 !important;
        color: white !important;
        border: none !important;
    }}

    /* Backend Status Bar */
    .backend-status-bar {{
        display: flex;
        align-items: center;
        gap: 0.55rem;
        background: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.55rem 0.9rem;
        margin-top: -1.5rem;
        margin-bottom: 1rem;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--text-main);
    }}

    .status-dot {{
        width: 9px;
        height: 9px;
        border-radius: 50%;
        flex-shrink: 0;
    }}

    .status-dot-online {{
        background-color: #4ADE80;
        box-shadow: 0 0 6px #4ADE80;
        animation: blink-green 1.6s ease-in-out infinite;
    }}

    .status-dot-offline {{
        background-color: #F87171;
        box-shadow: 0 0 6px #F87171;
        animation: blink-red 1.6s ease-in-out infinite;
    }}

    @keyframes blink-green {{
        0%, 100% {{ opacity: 1; box-shadow: 0 0 6px #4ADE80; }}
        50%        {{ opacity: 0.35; box-shadow: 0 0 2px #4ADE80; }}
    }}

    @keyframes blink-red {{
        0%, 100% {{ opacity: 1; box-shadow: 0 0 6px #F87171; }}
        50%        {{ opacity: 0.35; box-shadow: 0 0 2px #F87171; }}
    }}
    
    /* Primary Button Global Styling */
    [data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, #3B82F6, #8B5CF6) !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
        transition: all 0.3s ease !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
    }}
    [data-testid="baseButton-primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(139, 92, 246, 0.5) !important;
        background: linear-gradient(135deg, #60A5FA, #A78BFA) !important;
    }}
    [data-testid="baseButton-primary"]:active {{
        transform: translateY(1px) !important;
    }}

    </style>
    """

    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    backend_online = False
    try:
        r = requests.get(f"{backend_url}/health", timeout=10)
        backend_online = r.status_code < 500
    except Exception:
        try:
            r = requests.get(f"{backend_url}/", timeout=10)
            backend_online = r.status_code < 500
        except Exception:
            backend_online = False

    dot_class = "status-dot-online" if backend_online else "status-dot-offline"
    status_label = "Server Active 🔆" if backend_online else "Server Resting 😴"
    status_bar_html = f"""
    <div class="backend-status-bar">
        <span class="status-dot {dot_class}"></span>
        <span>{status_label}</span>
    </div>
    """

    with st.sidebar:
        st.markdown(custom_css, unsafe_allow_html=True)
        st.markdown(status_bar_html, unsafe_allow_html=True)
        
        config_dir = os.path.join(os.path.dirname(__file__), ".streamlit")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.toml")
        
        if st.session_state.theme == 'dark':
            toml_content = '''[theme]
primaryColor = "#3B82F6"
backgroundColor = "#0F172A"
secondaryBackgroundColor = "#1E293B"
textColor = "#F8FAFC"
font = "sans serif"

[server]
headless = true
port = 8501
'''
        else:
            toml_content = '''[theme]
primaryColor = "#2563EB"
backgroundColor = "#F8FAFC"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#0F172A"
font = "sans serif"

[server]
headless = true
port = 8501
'''
        current_toml = ""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                current_toml = f.read()
                
        if current_toml != toml_content:
            with open(config_path, "w") as f:
                f.write(toml_content)
            st.rerun()
