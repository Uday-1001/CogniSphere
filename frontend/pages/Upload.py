import streamlit as st
import requests
import os
import sys
from typing import Optional

st.set_page_config(
    page_title="AI Multimedia Assistant",
    layout="wide"
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_enhancer
ui_enhancer.apply_custom_theme()

API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

SUPPORTED_FORMATS = {
    "video":    ["mp4", "mov", "mkv", "avi", "webm"],
    "audio":    ["mp3", "wav", "m4a", "flac"],
    "document": ["pdf", "docx", "pptx", "txt"],
}

TYPE_META = {
    "video":    {"icon": "🎦", "label": "Video",    "color": "#C084FC"},
    "audio":    {"icon": "🎧️", "label": "Audio",    "color": "#4ADE80"},
    "document": {"icon": "📄", "label": "Document", "color": "#60A5FA"},
}


def get_file_type(filename: str) -> Optional[str]:
    file_extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    for format_category, valid_extensions in SUPPORTED_FORMATS.items():
        if file_extension in valid_extensions:
            return format_category
    return None


ERROR_HINTS = {
    "no text could be extracted": (
        "This file doesn't contain any readable text. It might be a scanned "
        "or image-based PDF. Try exporting it as a text-based PDF, or run OCR "
        "on it before uploading."
    ),
    "unsupported file type": "This file format isn't supported. Please upload a PDF, DOCX, PPTX, TXT, or multimedia file.",
    "file not found": "The file couldn't be found on the server. Please try uploading again.",
    "timeout": "The request timed out. The file may be too large — try a smaller file or check your connection.",
    "connection": "Could not reach the server. Make sure the backend is running.",
}


def friendly_error(response=None, exception: Optional[Exception] = None) -> str:
    raw = ""
    if exception is not None:
        raw = str(exception).lower()
        for keyword, hint in ERROR_HINTS.items():
            if keyword in raw:
                return hint
        return f"An unexpected error occurred: {exception}"
    if response is not None:
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = response.text
        raw = detail.lower()
        for keyword, hint in ERROR_HINTS.items():
            if keyword in raw:
                return hint
        return detail if detail else f"Server returned status {response.status_code}."
    return "An unknown error occurred."


def main():

    st.markdown(
        """
        <style>
        .format-pill {
            display: inline-block;
            padding: 0.35rem 0.8rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
            margin: 0.25rem 0.2rem;
            letter-spacing: 0.03em;
            transition: all 0.3s ease;
            backdrop-filter: blur(8px);
            cursor: default;
        }
        .format-pill:hover {
            transform: translateY(-2px);
        }
        .pill-video    { background: rgba(192,132,252,0.1); color: #D8B4FE; border: 1px solid rgba(192,132,252,0.25); box-shadow: 0 2px 10px rgba(192,132,252,0.1); }
        .pill-video:hover { background: rgba(192,132,252,0.2); box-shadow: 0 4px 15px rgba(192,132,252,0.2); }
        
        .pill-audio    { background: rgba(74,222,128,0.1);  color: #86EFAC; border: 1px solid rgba(74,222,128,0.25); box-shadow: 0 2px 10px rgba(74,222,128,0.1); }
        .pill-audio:hover { background: rgba(74,222,128,0.2); box-shadow: 0 4px 15px rgba(74,222,128,0.2); }
        
        .pill-document { background: rgba(96,165,250,0.1);  color: #93C5FD; border: 1px solid rgba(96,165,250,0.25); box-shadow: 0 2px 10px rgba(96,165,250,0.1); }
        .pill-document:hover { background: rgba(96,165,250,0.2); box-shadow: 0 4px 15px rgba(96,165,250,0.2); }

        /* Upload zone styling */
        [data-testid="stFileUploadDropzone"] {
            background: rgba(30, 41, 59, 0.3) !important;
            backdrop-filter: blur(12px) !important;
            border: 2px dashed rgba(255, 255, 255, 0.15) !important;
            border-radius: 20px !important;
            transition: all 0.3s ease !important;
            padding: 3rem !important;
        }
        [data-testid="stFileUploadDropzone"]:hover {
            border-color: var(--accent-color) !important;
            background: rgba(30, 41, 59, 0.5) !important;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.15) !important;
        }

        .info-card {
            background: linear-gradient(145deg, rgba(30, 41, 59, 0.6), rgba(15, 23, 42, 0.8));
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 1.5rem 1.75rem;
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.3);
            animation: fade-in-up 0.5s ease-out;
        }
        
        @keyframes fade-in-up {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .step-num {
            width: 28px; height: 28px;
            border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.85rem;
            margin-right: 0.6rem;
            flex-shrink: 0;
        </style>
        """,
        unsafe_allow_html=True,
    )


    st.markdown(
        """
        <div style="margin-bottom:0.25rem;">
            <span style="font-size:2rem; font-weight:800; color:var(--text-main);">
                📤 Add to Your Knowledge Base
            </span>
        </div>
        <div style="color:var(--text-muted); font-size:1rem; margin-bottom:1.5rem; max-width:620px;">
            Drop in a lecture video, a podcast episode, a research paper — 
            anything you want to be able to <b>ask questions about</b>. Leave the rest on Us.
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.markdown(
        """
        <div style="margin-bottom:2rem; display: flex; flex-direction: column; gap: 0.75rem;">
            <div style="font-size: 0.9rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Supported Formats</div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <span class="format-pill pill-video">🎬 MP4</span>
                <span class="format-pill pill-video">🎬 MOV</span>
                <span class="format-pill pill-video">🎬 MKV</span>
                <span class="format-pill pill-video">🎬 WEBM</span>
                <span class="format-pill pill-audio">🎙️ MP3</span>
                <span class="format-pill pill-audio">🎙️ WAV</span>
                <span class="format-pill pill-audio">🎙️ M4A</span>
                <span class="format-pill pill-document">📄 PDF</span>
                <span class="format-pill pill-document">📄 DOCX</span>
                <span class="format-pill pill-document">📄 PPTX</span>
                <span class="format-pill pill-document">📄 TXT</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


    uploaded_file = st.file_uploader(
        "👇 Drag & drop your file here, or click to browse",
        help="Up to 200 MB per file. Videos and audio are auto-transcribed with Whisper.",
        label_visibility="visible",
    )

    if uploaded_file:
        file_type = get_file_type(uploaded_file.name)
        meta = TYPE_META.get(file_type or "", {"icon": "📁", "label": "Unknown", "color": "#94A3B8"})
        size_mb = uploaded_file.size / (1024 * 1024)

        st.markdown("<br>", unsafe_allow_html=True)


        warning_html = "<div style='color:#FBBF24;font-size:0.85rem;margin-top:0.5rem;background:rgba(251,191,36,0.1);padding:0.4rem 0.8rem;border-radius:8px;display:inline-block;'><span style='margin-right:4px;'>⚠️</span>Audio/video will be transcribed — large files may take a few minutes.</div>" if file_type in ['video', 'audio'] else ""
        card_html = (
            '<div class="info-card" style="margin-bottom:1.5rem;">'
            '<div style="display:flex;align-items:center;gap:1.25rem;flex-wrap:wrap;">'
            f'<div style="font-size:2.8rem; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.2));">{meta["icon"]}</div>'
            '<div style="flex:1;min-width:180px;">'
            f'<div style="font-weight:700;color:var(--text-main);font-size:1.1rem;word-break:break-all;letter-spacing:0.02em;">{uploaded_file.name}</div>'
            '<div style="color:var(--text-muted);font-size:0.9rem;margin-top:0.25rem;">'
            f'<span style="color:{meta["color"]};font-weight:700;background:rgba(255,255,255,0.05);padding:0.15rem 0.5rem;border-radius:6px;font-size:0.8rem;">{meta["label"]}</span>'
            f'<span style="margin-left:0.5rem;">{size_mb:.2f} MB</span>'
            '</div>'
            + warning_html +
            '</div></div></div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)


        existing_file_id = st.session_state.get(f"uploaded_{uploaded_file.name}", {}).get("file_id")
        if not existing_file_id:
            try:
                docs_response = requests.get(f"{API_BASE_URL}/history/documents", timeout=5)
                if docs_response.status_code == 200:
                    for doc in docs_response.json():
                        if doc.get("filename") == uploaded_file.name:
                            existing_file_id = doc["id"]
                            st.session_state[f"uploaded_{uploaded_file.name}"] = {"file_id": existing_file_id}
                            break
            except Exception:
                pass

        if existing_file_id:
            view_url = f"{API_BASE_URL}/upload/{existing_file_id}/view"
            st.markdown(
                f'<a href="{view_url}" target="_blank" style="'
                'display:inline-flex;align-items:center;gap:0.5rem;'
                'padding:0.5rem 1.25rem;border-radius:10px;font-size:0.9rem;font-weight:600;'
                'background:rgba(96,165,250,0.15);color:#93C5FD;'
                'border:1px solid rgba(96,165,250,0.3);text-decoration:none;'
                'transition:all 0.2s ease;" '
                'onmouseover="this.style.background=\'rgba(96,165,250,0.25)\';this.style.transform=\'translateY(-1px)\'" '
                'onmouseout="this.style.background=\'rgba(96,165,250,0.15)\';this.style.transform=\'none\'">'
                '\U0001f441\ufe0f View File</a>',
                unsafe_allow_html=True,
            )
        st.markdown("<div style='margin-bottom:1rem'></div>", unsafe_allow_html=True)


        button_column, space_column = st.columns([2, 5])
        with button_column:
            if st.button(f"🚀 Upload & Process {uploaded_file.name[:30]}{'…' if len(uploaded_file.name)>30 else ''}",
                         type="primary", use_container_width=True):

                with st.status("📤 Uploading your file…", expanded=True) as status:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/upload/",
                            files=files,
                            timeout=60,
                        )
                        if response.status_code != 200:
                            err = friendly_error(response=response)
                            status.update(label="❌ Upload failed", state="error")
                            st.error(f"**Upload failed**\n\n{err}")
                            st.stop()

                        result = response.json()
                        file_id = result.get("file_id")
                        st.write(f"✅ File received with ID : `{file_id}`")


                        status.update(label="⚙️ Starting processing...", expanded=True)
                        process_response = requests.post(
                            f"{API_BASE_URL}/upload/{file_id}/process",
                            timeout=60,
                        )
                        
                        if process_response.status_code == 200:
                            import time
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            while True:
                                try:
                                    status_response = requests.get(f"{API_BASE_URL}/upload/{file_id}/status", timeout=10)
                                    if status_response.status_code == 200:
                                        status_data = status_response.json()
                                        current_step = status_data.get("current", 0)
                                        total_steps = status_data.get("total", 0)
                                        status_message = status_data.get("message", "Processing...")
                                        job_status = status_data.get("status")
                                        
                                        if total_steps > 0:
                                            progress_percentage = min(1.0, max(0.0, current_step / total_steps))
                                            progress_bar.progress(progress_percentage)
                                        
                                        status_text.markdown(f"**{status_message}**")
                                        
                                        if job_status == "processed":
                                            progress_bar.progress(1.0)
                                            st.write("✅ Indexing complete — ready to chat!")
                                            status.update(
                                                label="🎉 All done! Your file is now part of your knowledge base.",
                                                state="complete",
                                                expanded=False,
                                            )
                                            st.session_state[f"file_{file_id}"] = result

                                            st.session_state[f"uploaded_{uploaded_file.name}"] = {"file_id": file_id}
                                            break
                                        elif job_status == "error":
                                            status.update(label="❌ Processing failed", state="error")
                                            st.error(f"**Could not process this file**\n\n{status_message}")
                                            break
                                        
                                        time.sleep(0.2)
                                    else:
                                        time.sleep(0.2)
                                except Exception:
                                    time.sleep(0.2)
                                    
                        else:
                            error_message = friendly_error(response=process_response)
                            status.update(label="❌ Processing failed", state="error")
                            st.error(f"**Could not process this file**\n\n{error_message}")

                    except requests.exceptions.ConnectionError:
                        status.update(label="❌ Connection failed", state="error")
                        st.error(f"**Cannot reach the server.**\n\nMake sure the backend is running at `{API_BASE_URL}`.")
                    except requests.exceptions.Timeout:
                        status.update(label="❌ Timed out", state="error")
                        st.error("**The request timed out.**\n\nThe file may be very large. Try a smaller file or check your connection.")
                    except Exception as unexpected_error:
                        status.update(label="❌ Unexpected error", state="error")
                        st.error(f"**Something went wrong**\n\n{friendly_error(exception=unexpected_error)}")

    st.markdown("<br><br>", unsafe_allow_html=True)


    st.markdown(
        "<div style='color:var(--text-main); font-weight:800; font-size:1.5rem;"
        " margin-bottom:1.5rem;'>How it works</div>",
        unsafe_allow_html=True,
    )

    s1, s2, s3 = st.columns(3)
    steps = [
        (s1, "#60A5FA", "01", "Upload",
         "Drop any video, audio, or document file using the uploader above for its knowledge extraction."),
        (s2, "#C084FC", "02", "Auto-Process",
         "We transcribe audio/video with Whisper and extract text from documents — all automatically."),
        (s3, "#4ADE80", "03", "Chat",
         "Head to the Chat page and ask anything. Your file is now part of your knowledge base."),
    ]
    for col, color, num, label, body in steps:
        with col:
            st.markdown(
                f"""
                <div class="step-card" style="--step-color: {color};">
                    <div class="step-number" style="color:{color};">{num}</div>
                    <div class="step-title">{label}</div>
                    <div class="step-desc">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

if __name__ == "__main__":
    main()