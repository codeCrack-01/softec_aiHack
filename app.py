import streamlit as st
from PyPDF2 import PdfReader

from extract import *

st.set_page_config(page_title="JSON Data Packager", page_icon="⚙️")

st.title("📝 Student Data & Email Packager")

with st.form("student_profile_form"):
    st.subheader("Student Information")

    col1, col2 = st.columns(2)
    with col1:
        student_name = st.text_input("Full Name")
        degree = st.text_input("Degree")
        semester = st.number_input(
            "Semester", min_value=1, max_value=8, step=1, value=1
        )

    with col2:
        cgpa = st.number_input(
            "CGPA", min_value=0.00, max_value=4.00, step=0.01, format="%.2f"
        )
        location_preference = st.text_input("Location Preference")
        financial_need_input = st.radio(
            "Financial Need?", ["No", "Yes"], horizontal=True
        )

    skills = st.text_area("Skills (comma separated)")
    preferred_types = st.multiselect(
        "Preferred Types", ["Research", "Internship", "Full-time", "Open Source"]
    )
    past_experience = st.text_area("Past Experience")

    submitted = st.form_submit_button("Save Profile")

st.subheader("Email Files")
uploaded_files = st.file_uploader(
    "Upload email .pdf files", type="pdf", accept_multiple_files=True
)

if st.button("Process & Send to LangChain"):
    if not uploaded_files:
        st.warning("Please upload files to proceed.")
    else:
        email_data = []
        for uploaded_file in uploaded_files:
            try:
                reader = PdfReader(uploaded_file)
                content = "".join(
                    [
                        page.extract_text()
                        for page in reader.pages
                        if page.extract_text()
                    ]
                )
                email_data.append(
                    {"filename": uploaded_file.name, "body": content.strip()}
                )
            except Exception as e:
                st.error(f"Error reading {uploaded_file.name}: {e}")

        # Construct the final payload
        final_payload = {
            "student_profile": {
                "name": student_name,
                "degree": degree,
                "semester": semester,
                "cgpa": cgpa,
                "skills": [s.strip() for s in skills.split(",") if s.strip()],
                "preferred_types": preferred_types,
                "financial_need": True if financial_need_input == "Yes" else False,
                "location_preference": location_preference,
                "past_experience": [past_experience] if past_experience else [],
                "available_documents": [f.name for f in uploaded_files],
            },
            "emails": email_data,
        }

        with st.status("Analyzing opportunities...", expanded=True) as status:
            st.write("Extracting data from emails...")
            processed_emails = process_emails(email_data)

            st.write("Ranking matches...")
            ranked_emails = rank_emails(
                final_payload["student_profile"], processed_emails
            )

            st.write("Generating explanations...")
            output_emails = explain_emails(
                final_payload["student_profile"], ranked_emails
            )
            status.update(label="Analysis Complete!", state="complete", expanded=False)

        st.subheader("Match Results")

        if not output_emails:
            st.info("No relevant opportunities were found in the uploaded emails.")
        else:
            output_emails.sort(key=lambda x: x[1], reverse=True)

            for explanation, score in output_emails:
                if score >= 80:
                    emoji = "🚀"
                elif score >= 50:
                    emoji = "📈"
                else:
                    emoji = "💡"

                with st.expander(f"{emoji} Match Score: {score}/100"):
                    st.markdown(explanation)
