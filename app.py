import csv
import io
from datetime import date, datetime

import streamlit as st
from dotenv import load_dotenv

from scout.discovery import discover_scholarships, fetch_scholarship_details
from scout.extraction import build_scholarship_record
from scout.eligibility import match_eligibility
from scout.assistant import answer_question
from scout.pipeline import prepare_discovered_scholarships, safe_provider_call
from scout.reliability import configuration_status, deduplicate_and_validate
from scout.source_trust import annotate_source, assess_source
from scout.scholarship_intelligence import assess_deadline, build_comparison_rows
from scout.product_quality import readiness_items, readiness_summary, safe_csv_cell
import logging
import uuid

logger = logging.getLogger(__name__)
from database.db import (
    init_db,
    save_scholarship,
    list_saved_scholarships,
    update_application_status,
    init_reminders_table,
    create_reminder,
    list_reminders,
    update_reminder_completed,
    delete_reminder,
    workspace_id,
)

load_dotenv()
init_db()
init_reminders_table()

st.set_page_config(page_title="Scholarship Scout", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1450px;}
.hero {padding: 1.5rem 1.7rem; border-radius: 18px; border: 1px solid rgba(128,128,128,.25); margin-bottom: 1.2rem;}
.hero h1 {margin: 0 0 .35rem 0;}
.hero p {margin: 0; opacity: .8; font-size: 1.03rem;}
.small-note {font-size: .86rem; opacity: .75;}
</style>
<div class="hero"><h1>🎓 Scholarship Scout</h1><p>Discover opportunities, understand your preliminary fit, and keep applications organized.</p></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("👤 Student profile")
    state = st.selectbox("State / UT", ["Karnataka", "Andhra Pradesh", "Tamil Nadu", "Telangana", "Kerala", "Maharashtra", "Other"])
    course = st.selectbox("Course", ["B.E. / B.Tech", "B.Sc.", "B.Com.", "B.A.", "Diploma", "Other undergraduate"])
    branch = st.text_input("Branch / major", "Artificial Intelligence and Data Science")
    year = st.selectbox("Current year", ["1st year", "2nd year", "3rd year", "4th year", "Other"])
    college_type = st.selectbox("College type", ["Private", "Government", "Aided", "Other"])
    income = st.number_input("Annual household income (₹)", min_value=0, max_value=100000000, value=300000, step=25000)
    marks = st.number_input("Class 12 percentage", min_value=0.0, max_value=100.0, value=96.16, step=0.25)
    category = st.selectbox("Category", ["Prefer not to say", "General", "OBC", "SC", "ST", "EWS", "Other"])
    interests = st.multiselect("Scholarship interests", ["Merit-based", "Need-based", "Government", "Private foundation", "Engineering / STEM"], default=["Merit-based", "Need-based", "Government"])
    max_results = st.slider("Results to search", 5, 20, 10)

    st.divider()
    st.subheader("🔒 Your private workspace")
    workspace_code = st.text_input(
        "Workspace code (optional)", type="password",
        help="Saved scholarships and reminders are private to your workspace. Leave blank for a temporary workspace that is cleared when you close the tab. Use a long, unique code you can remember; anyone who knows it can see your tracker. Do not use your name, phone number or email.",
    )
    st.caption("Your profile is used for preliminary matching. It is not sent as a full personal identity profile to scholarship providers.")

profile = {
    "state": state, "course": course, "branch": branch.strip(), "year": year,
    "college_type": college_type, "income": int(income), "marks": float(marks),
    "category": category, "interests": interests,
}


if "guest_workspace" not in st.session_state:
    st.session_state["guest_workspace"] = "guest-" + uuid.uuid4().hex
WORKSPACE = workspace_id(workspace_code) if workspace_code.strip() else st.session_state["guest_workspace"]


def parse_deadline(value):
    if not value:
        return None
    value = str(value).strip()
    formats = ["%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %B %Y", "%d %b %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def deadline_label(value):
    parsed = parse_deadline(value)
    if not parsed:
        return "Date not verified", "Unknown"
    days = (parsed - date.today()).days
    if days < 0:
        return f"Possibly expired ({abs(days)} days ago)", "Expired?"
    if days <= 7:
        return f"{days} day(s) left", "Urgent"
    if days <= 30:
        return f"{days} days left", "Coming up"
    return f"{days} days left", "Upcoming"


def make_csv(items):
    buffer = io.StringIO()
    fields = ["name", "provider", "url", "application_url", "source_name", "application_cycle", "deadline", "income_limit", "academic_criteria", "benefits", "documents", "eligibility_text", "summary"]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({key: safe_csv_cell(item.get(key, "")) for key in fields})
    return buffer.getvalue().encode("utf-8-sig")

find_tab, saved_tab, reminders_tab, assistant_tab, about_tab = st.tabs(["🔎 Discover", "📌 My tracker", "📅 Deadlines & reminders", "🤖 AI assistant", "ℹ️ How it works"])

with find_tab:
    st.subheader("Scholarship discovery")
    st.write("Searches live web results with TinyFish. Always verify eligibility, dates, and application links on the official provider page.")
    search_col, clear_col = st.columns([3, 1])
    with search_col:
        run_search = st.button("🔍 Search scholarships", type="primary", use_container_width=True)
    with clear_col:
        clear_results = st.button("Clear results", use_container_width=True)
    if clear_results:
        st.session_state.pop("scholarships", None)
        st.session_state.pop("raw_results", None)
        st.session_state.pop("discovery_report", None)
        st.rerun()

    if run_search:
        with st.spinner("Searching scholarship sources and retrieving page details…"):
            search_response = safe_provider_call(
                discover_scholarships,
                profile,
                limit=max_results,
                provider_name="TinyFish Search",
            )
            if not search_response["ok"]:
                st.error(search_response["error"])
                st.info("Check that TINYFISH_API_KEY is configured locally and that your connection is available. Never paste API keys into chat.")
                st.session_state["scholarships"] = []
                st.session_state["discovery_report"] = {
                    "input_count": 0, "output_count": 0, "duplicates_removed": 0,
                    "validation_issues": [], "fetch_warning": None,
                }
            else:
                prepared = prepare_discovered_scholarships(
                    search_response["data"], source_label="TinyFish Search"
                )
                results = prepared["scholarships"]
                report = {
                    "input_count": prepared["input_count"],
                    "output_count": prepared["output_count"],
                    "duplicates_removed": prepared["duplicates_removed"],
                    "validation_issues": prepared["validation_issues"],
                    "fetch_warning": None,
                }

                if not results:
                    st.warning("TinyFish returned no usable scholarship records. Try a broader search or check the TinyFish connection.")
                    st.session_state["scholarships"] = []
                    st.session_state["raw_results"] = []
                    st.session_state["discovery_report"] = report
                else:
                    urls = [
                        r.get("url", "") for r in results
                        if isinstance(r.get("url"), str) and r.get("url", "").startswith(("http://", "https://"))
                    ]
                    fetch_response = safe_provider_call(
                        fetch_scholarship_details,
                        urls[:10],
                        provider_name="TinyFish Fetch",
                    )
                    pages = []
                    if fetch_response["ok"]:
                        pages_prepared = prepare_discovered_scholarships(
                            fetch_response["data"], source_label="TinyFish Fetch"
                        )
                        pages = pages_prepared["scholarships"]
                    else:
                        report["fetch_warning"] = fetch_response["error"]

                    page_by_url = {p.get("url"): p for p in pages if isinstance(p, dict) and p.get("url")}
                    page_by_final_url = {
                        p.get("final_url"): p for p in pages
                        if isinstance(p, dict) and p.get("final_url")
                    }

                    records = []
                    for result in results:
                        if not isinstance(result, dict):
                            continue
                        url = result.get("url", "")
                        page = page_by_url.get(url) or page_by_final_url.get(url) or {}
                        try:
                            record = build_scholarship_record(result, page, profile)
                            if not isinstance(record, dict):
                                logger.warning("Extraction returned a non-dictionary record; skipped")
                                continue
                            record["match"] = match_eligibility(record, profile)
                            records.append(record)
                        except Exception:
                            logger.exception("Failed to extract one scholarship result")
                            # Preserve the result as a minimal record rather than failing the entire search.
                            fallback = dict(result)
                            fallback.setdefault("name", fallback.get("title") or "Scholarship opportunity")
                            fallback.setdefault("summary", fallback.get("snippet") or "")
                            fallback.setdefault("page_text_excerpt", "")
                            fallback["match"] = {
                                "status": "Needs verification", "score": 0,
                                "reason": "Automatic extraction failed for this result.",
                                "evidence": [], "concerns": ["Verify details directly on the source page."],
                                "mismatches": [],
                                "score_note": "Preliminary score only; not a probability of receiving an award.",
                            }
                            records.append(fallback)

                    records, record_issues = deduplicate_and_validate(records)
                    # Recalculate match if an extractor's returned record had no match.
                    for record in records:
                        if not isinstance(record.get("match"), dict):
                            record["match"] = match_eligibility(record, profile)

                    # Keep source-level and extracted-record issues visible without blocking useful results.
                    issue_map = {}
                    for issue in report["validation_issues"] + record_issues:
                        key = issue.get("name", "(unnamed record)")
                        issue_map.setdefault(key, [])
                        issue_map[key].extend(issue.get("issues", []))
                    report["validation_issues"] = [
                        {"name": name, "issues": sorted(set(issues))}
                        for name, issues in issue_map.items()
                    ]
                    report["output_count"] = len(records)
                    report["duplicates_removed"] += max(0, len(prepared["scholarships"]) - len(records))

                    st.session_state["raw_results"] = results
                    st.session_state["scholarships"] = records
                    st.session_state["discovery_report"] = report

                    if report["fetch_warning"]:
                        st.warning("Page details could not be fetched. Results are shown using search snippets where possible.")

    report = st.session_state.get("discovery_report", {})
    if report:
        st.markdown("#### Discovery quality report")
        q1, q2, q3 = st.columns(3)
        q1.metric("Search results received", report.get("input_count", 0))
        q2.metric("Usable unique records", report.get("output_count", 0))
        q3.metric("Duplicates removed", report.get("duplicates_removed", 0))
        if report.get("validation_issues"):
            with st.expander(f"⚠️ Data-quality checks ({len(report['validation_issues'])})"):
                for issue in report["validation_issues"]:
                    st.warning(f"{issue['name']}: {'; '.join(issue['issues'])}")
        else:
            st.caption("No basic data-quality warnings were detected. This does not verify factual accuracy.")
        source_counts = {"strong": 0, "institutional": 0, "organisation": 0, "general": 0, "unknown": 0}
        for record in st.session_state.get("scholarships", []):
            source_counts[assess_source(record).get("level", "unknown")] += 1
        st.caption(
            "Source-origin signals (heuristic, not verification): "
            f"government-domain {source_counts['strong']} · education-domain {source_counts['institutional']} · "
            f"organisation-domain {source_counts['organisation']} · general web {source_counts['general']} · "
            f"unknown source {source_counts['unknown']}"
        )
    with st.expander("🔧 Configuration check (safe; no keys shown)"):
        config = configuration_status()
        st.write("TinyFish API key configured:", "Yes" if config["tinyfish_configured"] else "No")
        st.write("Gemini API key configured:", "Yes" if config["gemini_configured"] else "No")
        st.write("Gemini model:", config["gemini_model"])
        st.caption("Configured does not guarantee service availability. API key values are never displayed.")

    records = st.session_state.get("scholarships", [])
    if records:
        eligible_count = sum(1 for r in records if r.get("match", {}).get("status") in ("Strong match", "Potential match"))
        verify_count = sum(1 for r in records if r.get("match", {}).get("status") == "Needs verification")
        saved_urls = {r.get("url") for r in list_saved_scholarships(workspace=WORKSPACE)}
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Results", len(records))
        m2.metric("Potential matches", eligible_count)
        m3.metric("Need verification", verify_count)
        m4.metric("Already saved", sum(1 for r in records if r.get("url") in saved_urls))

        f1, f2, f3 = st.columns([2, 1, 1])
        search_text = f1.text_input("Filter results", placeholder="Search by scholarship, provider, benefit…", key="filter_text")
        status_options = ["All statuses", "Strong match", "Potential match", "Needs verification", "Likely ineligible"]
        status_filter = f2.selectbox("Match status", status_options)
        sort_by = f3.selectbox("Sort by", ["Best preliminary fit", "Name A–Z", "Deadline first"])

        filtered = []
        for item in records:
            blob = " ".join(str(item.get(k, "")) for k in ["name", "source_name", "summary", "benefits", "snippet"]).lower()
            if search_text.lower().strip() and search_text.lower().strip() not in blob:
                continue
            status = item.get("match", {}).get("status", "Needs verification")
            if status_filter != "All statuses" and status != status_filter:
                continue
            filtered.append(item)
        if sort_by == "Name A–Z":
            filtered.sort(key=lambda x: (x.get("name") or "").lower())
        elif sort_by == "Deadline first":
            filtered.sort(key=lambda x: parse_deadline(x.get("deadline")) or date.max)
        else:
            rank = {"Strong match": 0, "Potential match": 1, "Needs verification": 2, "Likely ineligible": 3}
            filtered.sort(key=lambda x: rank.get(x.get("match", {}).get("status"), 1))

        st.markdown("#### ⚖️ Compare scholarships")
        st.caption("Choose up to 4 results to compare the details currently extracted from their source pages. Missing values remain unknown; this is not an award recommendation.")
        compare_labels = []
        compare_by_label = {}
        for idx, rec in enumerate(filtered):
            base_label = str(rec.get("name") or rec.get("title") or f"Scholarship {idx + 1}").strip()
            label = f"{base_label} · result {idx + 1}"
            compare_labels.append(label)
            compare_by_label[label] = rec
        selected_compare = st.multiselect(
            "Select scholarships to compare (maximum 4)",
            options=compare_labels,
            default=[],
            max_selections=4,
            key="phase10_compare_selection",
        )
        if selected_compare:
            comparison_rows = build_comparison_rows([compare_by_label[label] for label in selected_compare])
            st.dataframe(comparison_rows, use_container_width=True, hide_index=True)
            st.caption("Comparison values are extracted data. Confirm every important detail on the provider's official page before applying.")

        st.download_button("⬇️ Export results as CSV", data=make_csv(filtered), file_name="scholarship_scout_results.csv", mime="text/csv")
        st.caption(f"Showing {len(filtered)} of {len(records)} results. Match labels are estimates based on incomplete page extraction.")
        if not filtered:
            st.info("No results match these filters. Try a different search term or status.")

        for i, item in enumerate(filtered):
            match = item.get("match", {})
            deadline_text, deadline_status = deadline_label(item.get("deadline"))
            with st.container(border=True):
                title = item.get("name") or item.get("title") or "Scholarship opportunity"
                st.markdown(f"### {title}")
                source_signal = assess_source(item)
                st.markdown(f"**Source signal:** {source_signal['label']} · `{source_signal['domain']}`")
                st.caption(source_signal["note"])
                c1, c2, c3 = st.columns([1, 1, 1])
                c1.metric("Preliminary fit", match.get("status", "Needs verification"), f"{match.get('score', 0)}/100")
                c2.metric("Deadline", item.get("deadline") or "Unknown")
                c3.metric("Deadline note", deadline_status)
                deadline_review = assess_deadline(item.get("deadline"))
                st.info(f"Deadline review: **{deadline_review['label']}** — {deadline_review['note']}")
                official_check_url = item.get("url", "")
                application_check_url = item.get("application_url", "")
                check_url = application_check_url if application_check_url.startswith(("http://", "https://")) else official_check_url
                if check_url.startswith(("http://", "https://")):
                    st.link_button("Open source to check deadline ↗", check_url, key=f"deadline_source_{i}")
                st.checkbox(
                    "I checked the deadline on the provider's source page",
                    key=f"deadline_checked_{i}_{str(item.get('url', ''))[:24]}",
                    help="This is a local session checklist only. It does not verify the date automatically or save a permanent verification record.",
                )
                st.write(item.get("summary") or item.get("snippet") or "No summary was extracted from the page.")
                st.write("**Why this status?** " + match.get("reason", "Not enough reliable information."))
                st.caption(match.get("score_note", "Preliminary score only; not a probability of receiving an award."))
                with st.expander("Eligibility evidence and items to verify"):
                    evidence = match.get("evidence", [])
                    concerns = match.get("concerns", [])
                    mismatches = match.get("mismatches", [])
                    if evidence:
                        st.markdown("**Evidence found**")
                        for note in evidence:
                            st.markdown(f"- {note}")
                    if concerns:
                        st.markdown("**Needs verification**")
                        for note in concerns:
                            st.markdown(f"- {note}")
                    if mismatches:
                        st.markdown("**Possible mandatory mismatches**")
                        for note in mismatches:
                            st.markdown(f"- {note}")
                    if not (evidence or concerns or mismatches):
                        st.write("No structured evidence was extracted.")
                d1, d2 = st.columns(2)
                with d1:
                    st.write("**Benefits**")
                    st.write(item.get("benefits") or "Not found in extracted text; check provider page.")
                    st.write("**Income condition found**")
                    st.write(item.get("income_limit") or "Unknown")
                with d2:
                    st.write("**Required documents**")
                    st.write(item.get("documents") or "Not found in extracted text; check provider page.")
                    st.write("**Source**")
                    st.write(item.get("source_name") or "Search result")
                with st.expander("📄 Detailed scholarship profile"):
                    st.write("**Provider / administering organization**")
                    st.write(item.get("provider") or "Not confidently extracted; verify on the source page.")
                    st.write("**Application cycle**")
                    st.write(item.get("application_cycle") or "Not found")
                    st.write("**Academic criteria found**")
                    st.write(item.get("academic_criteria") or "Not confidently extracted")
                    st.write("**Eligibility text found**")
                    st.write(item.get("eligibility_text") or "Not confidently extracted")
                    st.caption(item.get("detail_extraction_note", "Verify all extracted information with the provider."))
                url = item.get("url", "")
                application_url = item.get("application_url", "")
                if application_url.startswith("http"):
                    st.link_button("Open application link ↗", application_url, use_container_width=True)
                elif url.startswith("http"):
                    st.link_button("Open source page to verify / apply ↗", url, use_container_width=True)
                save_col, note_col = st.columns([1, 3])
                with save_col:
                    if url in saved_urls:
                        st.button("✓ Saved", key=f"saved_disabled_{i}", disabled=True, use_container_width=True)
                    elif st.button("☆ Save to tracker", key=f"save_{i}", use_container_width=True):
                        save_scholarship(item, workspace=WORKSPACE)
                        st.toast("Saved to your tracker")
                        st.rerun()
                with note_col:
                    st.caption("Verify the current application cycle and eligibility directly with the provider before relying on this result.")
    else:
        st.info("Set your profile in the sidebar, then search to discover live opportunities. No sample scholarships are fabricated.")

with saved_tab:
    st.subheader("My scholarship tracker")
    saved = list_saved_scholarships(workspace=WORKSPACE)
    if not saved:
        st.info("Your tracker is empty. Discover scholarships and save the opportunities you want to follow.")
    else:
        statuses = ["Interested", "Planning to apply", "Applied", "Awarded", "Not eligible", "Closed"]
        total, applied, awarded = st.columns(3)
        total.metric("Saved", len(saved))
        applied.metric("Applied", sum(1 for x in saved if x.get("application_status") == "Applied"))
        awarded.metric("Awarded", sum(1 for x in saved if x.get("application_status") == "Awarded"))
        tracker_filter = st.selectbox("Filter by application status", ["All"] + statuses)
        visible = [r for r in saved if tracker_filter == "All" or r.get("application_status", "Interested") == tracker_filter]
        st.download_button("⬇️ Export saved tracker as CSV", data=make_csv(visible), file_name="my_scholarship_tracker.csv", mime="text/csv")
        for row in visible:
            with st.container(border=True):
                st.markdown(f"### {row.get('name') or 'Scholarship opportunity'}")
                dlabel, dstatus = deadline_label(row.get("deadline"))
                st.write(f"**Deadline:** {row.get('deadline') or 'Unknown'} · **Deadline note:** {dlabel}")
                st.write(f"**Provider/source:** {row.get('source_name') or 'Unknown'} · **Last saved/checked:** {row.get('last_checked') or 'Unknown'}")
                with st.expander("✅ Application readiness checklist", expanded=False):
                    st.caption("A manual checklist to help you prepare. Checking an item records your progress only for this browser session; it does not independently verify facts or save progress to the database.")
                    completed_keys = []
                    for checklist_key, checklist_label in readiness_items():
                        key = f"readiness_{row['id']}_{checklist_key}"
                        if st.checkbox(checklist_label, key=key):
                            completed_keys.append(checklist_key)
                    readiness = readiness_summary(completed_keys)
                    st.progress(readiness["percent"] / 100, text=f"{readiness['completed']} of {readiness['total']} steps checked")
                    if readiness["is_complete"]:
                        st.success("Checklist complete. Recheck the provider's current instructions before submitting.")
                url = row.get("application_url") or row.get("url", "")
                if url.startswith("http"):
                    st.link_button("Open application / source page ↗", url)
                current = row.get("application_status", "Interested")
                c1, c2 = st.columns([2, 1])
                new_status = c1.selectbox("Application status", statuses, index=statuses.index(current) if current in statuses else 0, key=f"status_{row['id']}")
                if c2.button("Update status", key=f"update_{row['id']}", use_container_width=True):
                    update_application_status(row["id"], new_status, workspace=WORKSPACE)
                    st.success("Application status updated.")
                    st.rerun()
                with st.expander("＋ Add a reminder for this scholarship"):
                    default_reminder_date = parse_deadline(row.get("deadline")) or date.today()
                    reminder_date = st.date_input(
                        "Remind me on",
                        value=default_reminder_date,
                        key=f"reminder_date_{row['id']}",
                    )
                    reminder_note = st.text_input(
                        "Reminder note",
                        value="Check requirements and submit application",
                        key=f"reminder_note_{row['id']}",
                    )
                    if st.button("Save reminder", key=f"create_reminder_{row['id']}", type="primary"):
                        create_reminder(row["id"], row.get("name") or "Scholarship opportunity", reminder_date.isoformat(), reminder_note.strip(), workspace=WORKSPACE)
                        st.success("Reminder saved. It will appear in the Deadlines & reminders tab.")
                        st.rerun()

with reminders_tab:
    st.subheader("📅 Deadlines & reminders")
    st.caption("These are in-app reminders stored locally in your SQLite database. They do not send email, SMS, push notifications, or run background monitoring.")
    reminders = list_reminders(workspace=WORKSPACE)
    today = date.today()
    pending = [r for r in reminders if not r.get("completed")]
    overdue = [r for r in pending if r.get("reminder_date") and r["reminder_date"] < today.isoformat()]
    due_today = [r for r in pending if r.get("reminder_date") == today.isoformat()]
    upcoming = [r for r in pending if r.get("reminder_date") and r["reminder_date"] > today.isoformat()]
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Pending reminders", len(pending))
    mc2.metric("Overdue", len(overdue))
    mc3.metric("Due today", len(due_today))
    mc4.metric("Upcoming", len(upcoming))
    if pending:
        st.markdown("#### Calendar overview")
        cal_rows = []
        for r in pending:
            try:
                rd = date.fromisoformat(r["reminder_date"])
                days = (rd - today).days
                if days < 0:
                    urgency = f"Overdue by {abs(days)} day(s)"
                elif days == 0:
                    urgency = "Due today"
                elif days <= 7:
                    urgency = f"In {days} day(s)"
                else:
                    urgency = f"In {days} days"
            except (ValueError, TypeError):
                urgency = "Date needs checking"
            cal_rows.append({
                "Reminder date": r.get("reminder_date", ""),
                "Scholarship": r.get("scholarship_name", ""),
                "Status": urgency,
                "Note": r.get("note", ""),
            })
        st.dataframe(cal_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No pending reminders yet. Add one from a saved scholarship in My tracker.")

    st.markdown("#### Manage reminders")
    if reminders:
        for reminder in reminders:
            with st.container(border=True):
                r1, r2, r3 = st.columns([3, 2, 1])
                r1.markdown(f"**{reminder.get('scholarship_name', 'Scholarship')}**")
                r1.caption(reminder.get("note") or "No note")
                r2.write(f"Date: {reminder.get('reminder_date', 'Unknown')}")
                r2.write("Completed" if reminder.get("completed") else "Pending")
                if reminder.get("completed"):
                    if r3.button("Reopen", key=f"reopen_reminder_{reminder['id']}"):
                        update_reminder_completed(reminder["id"], False, workspace=WORKSPACE)
                        st.rerun()
                else:
                    if r3.button("Complete", key=f"complete_reminder_{reminder['id']}"):
                        update_reminder_completed(reminder["id"], True, workspace=WORKSPACE)
                        st.rerun()
                with st.expander("Reminder actions", key=f"reminder_actions_{reminder['id']}"):
                    if st.button("Delete reminder", key=f"delete_reminder_{reminder['id']}"):
                        delete_reminder(reminder["id"], workspace=WORKSPACE)
                        st.rerun()
    else:
        st.caption("Saved reminders will appear here.")

with assistant_tab:
    st.subheader("🤖 Scholarship Assistant")
    st.write("Ask about scholarships in your current search results or saved tracker. Answers are grounded in the records available to this app.")
    if __import__("os").getenv("GEMINI_API_KEY", "").strip():
        st.success("Gemini assistant mode is configured. Answers still use only the scholarship records provided to the assistant.")
    else:
        st.info("Local source-grounded mode is active. To enable generative AI answers, add GEMINI_API_KEY to your local .env file. No API key is required to use the basic assistant.")
    assistant_items = []
    assistant_items.extend(st.session_state.get("scholarships", []))
    assistant_items.extend(list_saved_scholarships(workspace=WORKSPACE))
    deduped_items = []
    seen_assistant_urls = set()
    for assistant_item in assistant_items:
        assistant_url = assistant_item.get("url", "")
        if assistant_url and assistant_url in seen_assistant_urls:
            continue
        if assistant_url:
            seen_assistant_urls.add(assistant_url)
        deduped_items.append(assistant_item)
    if not deduped_items:
        st.warning("Search for scholarships or save opportunities first. The assistant does not invent a scholarship catalogue.")
    with st.form("scholarship_assistant_form"):
        question = st.text_area(
            "Your question",
            placeholder="Example: Which saved scholarships list an income limit? What documents should I verify?",
            height=100,
        )
        ask = st.form_submit_button("Ask Scholarship Scout", type="primary")
    if ask:
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            with st.spinner("Reviewing available scholarship sources…"):
                result = answer_question(question, profile, deduped_items)
            st.session_state["assistant_last_answer"] = result
            st.session_state["assistant_last_question"] = question
    last_answer = st.session_state.get("assistant_last_answer")
    if last_answer:
        st.markdown("#### Answer")

        # Make it clear whether Gemini or the local fallback supplied the answer.
        mode = last_answer.get("mode", "local")
        if mode == "gemini":
            st.success("🤖 Answer generated by Gemini")
        else:
            st.info("📚 Answer generated using the local source-grounded fallback")

        st.markdown(last_answer.get("answer", "No answer returned."))

        sources = last_answer.get("sources", [])
        if sources:
            st.markdown("#### Sources used")
            for idx, source in enumerate(sources, start=1):
                source_name = (
                    source.get("name")
                    or source.get("title")
                    or "Scholarship source"
                )
                source_url = (
                    source.get("application_url")
                    or source.get("url")
                    or ""
                )
                st.write(f"{idx}. **{source_name}**")
                if source_url.startswith(("http://", "https://")):
                    st.link_button(
                        f"Open source: {source_name}",
                        source_url,
                        key=f"assistant_source_{idx}",
                    )

        st.caption(
            "Verify important eligibility rules, award amounts, and current "
            "deadlines directly with the official provider."
        )

with about_tab:
    st.subheader("How Scholarship Scout works")
    st.markdown("""
    1. **Discover:** TinyFish Search finds candidate scholarship pages.
    2. **Fetch:** TinyFish Fetch retrieves page content for selected results.
    3. **Extract:** Lightweight rules look for names, deadlines, income conditions, benefits, documents, academic criteria, provider names, and application-cycle hints.
    4. **Match:** Transparent rules compare extracted information with your profile and show evidence, concerns, and a preliminary criteria-coverage score.
    5. **Track:** Save opportunities, update application status, create in-app reminders, and export your tracker.
    6. **Ask:** The Scholarship Assistant answers using current search results and saved records. Gemini is optional; without its API key, the app uses a basic source-grounded local mode.

    **Important limitations**
    - Search results do not prove that a scholarship is currently open.
    - Extracted details can be incomplete, ambiguous, or from an older application cycle.
    - A preliminary match is not an official eligibility decision or a guarantee of funding.
    - The 0–100 score reflects extracted criteria coverage, not the probability of receiving an award. Extraction may miss or misinterpret requirements.
    - Date labels are only as reliable as the extracted date and supported date format.
    - A separate application URL is shown only if the fetch response explicitly provides one; otherwise, open the source page and verify the official application route.
    - Reminders are stored in the local database and appear when you open the app; they do not send email/SMS/push notifications or run when the app is closed.
    - The assistant can only reason from records currently available to it. Its answers may omit facts that were not extracted from source pages. If Gemini is enabled, scholarship excerpts and the relevant profile fields are sent to the Gemini API for answering; do not enter sensitive personal identifiers.
    - The app does not submit applications, upload documents, or automatically monitor deadlines in the background.
    - Always confirm details on the legitimate provider website before applying.
    """)
    st.caption("Scholarship Scout · Python · Streamlit · SQLite · TinyFish Search/Fetch")
