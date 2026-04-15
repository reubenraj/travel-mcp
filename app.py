"""
app.py

Streamlit chat interface for the arrivia AI Travel Concierge.
Talks to the FastAPI recommendation service at /recommend.

Run with:
    streamlit run app.py
"""

import httpx
import streamlit as st

API_URL            = "http://localhost:8000"
MEMBER_SERVICE_URL = "http://localhost:8001"

TIER_COLORS = {
    "Platinum": "#534AB7",
    "Gold":     "#BA7517",
    "Silver":   "#5F5E5A",
}


# ── Dynamic member loader ──────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_members() -> dict:
    """
    Fetches the live member list from the member service.
    Cached for 60 seconds — won't hammer the service on every rerender.
    Returns a dict keyed by member_id.
    """
    try:
        response = httpx.get(f"{MEMBER_SERVICE_URL}/members", timeout=10.0)
        response.raise_for_status()
        members = {}
        for m in response.json():
            history = m.get("travel_history", [])
            last_trip = (
                f"{history[0]['destination']} ({history[0]['travel_date'][:7]})"
                if history else "No trips on file"
            )
            members[m["member_id"]] = {
                "name":      m["name"],
                "tier":      m["loyalty_tier"],
                "partner":   m["partner_id"],
                "partner_name": m["partner_name"],
                "last_trip": last_trip,
            }
        return members
    except httpx.ConnectError:
        st.error("Cannot reach member service on port 8001. Is it running?")
        return {}
    except Exception as e:
        st.error(f"Failed to load members: {e}")
        return {}


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Travel Concierge",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
    .user-msg {
        background: #185FA5;
        color: #E6F1FB;
        padding: 10px 14px;
        border-radius: 12px;
        margin: 4px 0;
        max-width: 85%;
        margin-left: auto;
        font-size: 14px;
        line-height: 1.5;
    }
    .assistant-msg {
        background: #f5f5f3;
        color: #1a1a1a;
        padding: 10px 14px;
        border-radius: 12px;
        margin: 4px 0;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.5;
        border: 0.5px solid #e0dfd8;
    }
    .msg-label  { font-size: 11px; color: #888780; margin-bottom: 2px; }
    .user-label { text-align: right; font-size: 11px; color: #888780; margin-bottom: 2px; }
    .tool-badge {
        display: inline-block;
        background: #E1F5EE;
        color: #085041;
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
        border-radius: 99px;
        margin: 2px 2px 2px 0;
    }
    .log-ok   { border-left: 3px solid #1D9E75; padding-left: 8px; font-size: 12px; color: #085041; margin: 3px 0; }
    .log-warn { border-left: 3px solid #EF9F27; padding-left: 8px; font-size: 12px; color: #633806; margin: 3px 0; }
    .log-info { border-left: 3px solid #85B7EB; padding-left: 8px; font-size: 12px; color: #0C447C; margin: 3px 0; }
    .tier-pill { display: inline-block; font-size: 11px; font-weight: 500; padding: 2px 10px; border-radius: 99px; margin-left: 6px; }
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "messages"              not in st.session_state: st.session_state.messages              = []
if "selected_member_id"    not in st.session_state: st.session_state.selected_member_id    = "MBR005"
if "last_tools_called"     not in st.session_state: st.session_state.last_tools_called     = []
if "last_enforcement_log"  not in st.session_state: st.session_state.last_enforcement_log  = []
if "last_partner_name"     not in st.session_state: st.session_state.last_partner_name     = ""

# ── Load live member catalog ───────────────────────────────────────────────────
MEMBERS = load_members()
if not MEMBERS:
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Session setup")

    member_options = {mid: f"{mid} — {info['name']}" for mid, info in MEMBERS.items()}
    selected_id = st.selectbox(
        "Member",
        options=list(member_options.keys()),
        format_func=lambda x: member_options[x],
        index=list(member_options.keys()).index(st.session_state.selected_member_id),
        key="member_select"
    )

    if selected_id != st.session_state.selected_member_id:
        st.session_state.selected_member_id    = selected_id
        st.session_state.messages              = []
        st.session_state.last_tools_called     = []
        st.session_state.last_enforcement_log  = []
        st.session_state.last_partner_name     = ""
        st.rerun()

    member = MEMBERS[selected_id]
    tier_color = TIER_COLORS.get(member["tier"], "#888780")

    st.markdown(f"""
    <div style="background:white;border:0.5px solid #e0dfd8;border-radius:10px;padding:12px 14px;margin:8px 0">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
            <span style="font-size:14px;font-weight:500;color:#1a1a1a">{member['name']}</span>
            <span class="tier-pill" style="background:{tier_color}1a;color:{tier_color}">{member['tier']}</span>
        </div>
        <div style="font-size:12px;color:#888780;margin-bottom:4px">{member['partner_name']}</div>
        <div style="font-size:12px;color:#888780">Last trip: {member['last_trip']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("**Tools called**")
    if st.session_state.last_tools_called:
        for tool in st.session_state.last_tools_called:
            st.markdown(f'<span class="tool-badge">{tool}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="font-size:12px;color:#888780">None yet — send a message</span>', unsafe_allow_html=True)

    st.divider()

    st.markdown("**Rules enforcement log**")
    if st.session_state.last_enforcement_log:
        for entry in st.session_state.last_enforcement_log:
            e = entry.lower()
            if "removed" in e or "truncated" in e or "cap" in e:
                css_class = "log-warn"
            elif "complete" in e or "returning" in e:
                css_class = "log-ok"
            else:
                css_class = "log-info"
            st.markdown(f'<div class="{css_class}"><span style="color:#fff">{entry}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="font-size:12px;color:#888780">No requests yet</span>', unsafe_allow_html=True)

    st.divider()

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages             = []
        st.session_state.last_tools_called    = []
        st.session_state.last_enforcement_log = []
        st.session_state.last_partner_name    = ""
        st.rerun()

# ── Main area ──────────────────────────────────────────────────────────────────
partner_label = st.session_state.last_partner_name or member["partner_name"]
st.markdown(
    f"#### AI Travel Concierge &nbsp;"
    f'<span style="font-size:13px;font-weight:400;color:#888780">'
    f"Powered by arrivia · {partner_label} portal</span>",
    unsafe_allow_html=True
)
st.divider()

if not st.session_state.messages:
    st.markdown(
        '<div class="msg-label">AI Concierge</div>'
        '<div class="assistant-msg">'
        "Hello! I'm your AI travel concierge. Ask me anything about travel "
        "recommendations — I'll personalise suggestions based on your history and loyalty tier."
        "</div>",
        unsafe_allow_html=True
    )

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="user-label">You</div>'
            f'<div class="user-msg">{msg["content"]}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="msg-label">AI Concierge</div>'
            f'<div class="assistant-msg">{msg["content"]}</div>',
            unsafe_allow_html=True
        )

# ── Chat input ─────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask about travel recommendations...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Render the user message immediately — before the API call blocks the UI
    st.markdown(
        f'<div class="user-label">You</div>'
        f'<div class="user-msg">{user_input}</div>',
        unsafe_allow_html=True
    )

    with st.spinner("AI Concierge is thinking..."):
        try:
            response = httpx.post(
                f"{API_URL}/recommend",
                json={"member_id": selected_id, "message": user_input},
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()

            st.session_state.last_tools_called    = data.get("tools_called", [])
            st.session_state.last_enforcement_log = data.get("enforcement_log", [])
            st.session_state.last_partner_name    = data.get("partner_name", "")
            st.session_state.messages.append({"role": "assistant", "content": data.get("ai_response", "Sorry, no response.")})

        except httpx.ConnectError:
            st.error("Cannot connect to the API. Is `uvicorn main:app --port 8000` running?")
        except httpx.HTTPStatusError as e:
            st.error(f"API error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")

    st.rerun()