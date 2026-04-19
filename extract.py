import json
import os
from datetime import date, datetime

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from prompts import *

load_dotenv()

llm = ChatGroq(groq_api_key=os.getenv("GROQ_API_KEY"), model="openai/gpt-oss-120b")  # type: ignore


def process_emails(emails):
    processed_emails = []
    for email in emails:
        print(f"Processing email: {email.get('filename', 'N/A')}")
        formatted_extraction_prompt = EXTRACTION_PROMPT.format(email_text=email["body"])

        llm_response_content = get_llm_response(
            formatted_extraction_prompt,
            "Please extract the information from the email above according to the system prompt.",
        )

        print(
            f"Raw LLM response for {email.get('filename', 'N/A')}:\n{llm_response_content[:500]}..."
        )

        try:
            cleaned_response = llm_response_content.strip()  # type: ignore
            if cleaned_response.startswith("```json") and cleaned_response.endswith(
                "```"
            ):
                cleaned_response = cleaned_response[7:-3].strip()
            elif cleaned_response.startswith("```") and cleaned_response.endswith(
                "```"
            ):
                cleaned_response = cleaned_response[3:-3].strip()

            p_email_dict = json.loads(cleaned_response)
            processed_emails.append(p_email_dict)
            print(
                f"Successfully parsed LLM response for {email.get('filename', 'N/A')}."
            )
        except json.JSONDecodeError as e:
            print(
                f"Error decoding JSON from LLM response for {email.get('filename', 'N/A')}: {e}"
            )
            print(f"LLM response (after stripping): {cleaned_response[:500]}...")  # type: ignore
            processed_emails.append(
                {
                    "is_opportunity": False,
                    "error": "JSON Decode Error",
                    "original_email": email.get("filename", "N/A"),
                    "llm_raw_response": llm_response_content,
                }
            )
        except Exception as e:
            print(
                f"An unexpected error occurred during JSON parsing for {email.get('filename', 'N/A')}: {e}"
            )
            processed_emails.append(
                {
                    "is_opportunity": False,
                    "error": "Unexpected Parsing Error",
                    "original_email": email.get("filename", "N/A"),
                    "llm_raw_response": llm_response_content,
                }
            )
    return processed_emails


def rank_emails(student_profile, processed_emails):
    ranked_emails = []

    for email in processed_emails:
        if (
            not isinstance(email, dict)
            or not email.get("is_opportunity")
            or email.get("error")
        ):
            continue

        score = 0

        eligibility = email.get("eligibility", {})

        required_degree = eligibility.get("required_degree")
        if required_degree in (None, ""):
            score += 15
        elif (
            student_profile.get("degree", "").lower() == (required_degree or "").lower()
        ):
            score += 15

        required_cgpa = eligibility.get("required_cgpa")
        if required_cgpa is None or required_cgpa == 0.0:
            score += 20
        elif student_profile.get("cgpa", 0.0) >= (required_cgpa or 0.0):
            score += 20

        sem = student_profile.get("semester")
        sem_min = eligibility.get("required_semester_min")
        sem_max = eligibility.get("required_semester_max")
        if sem_min is None and sem_max is None:
            score += 10
        elif (sem is not None and (sem_min is None or sem >= sem_min)) and (
            sem is not None and (sem_max is None or sem <= sem_max)
        ):
            score += 10

        # --- Skills match (Medium weight) ---
        required_skills = set(s.lower() for s in eligibility.get("required_skills", []))
        student_skills = set(s.lower() for s in student_profile.get("skills", []))

        if not required_skills:
            score += 10
        else:
            match_ratio = len(student_skills & required_skills) / len(required_skills)
            score += round(match_ratio * 10)

        if email.get("type") in student_profile.get("preferred_types", []):
            score += 10

        if student_profile.get("financial_need", False) and eligibility.get(
            "financial_aid_available", False
        ):
            score += 5

        required_location = eligibility.get("location")
        if required_location in (None, ""):
            score += 5
        elif (
            student_profile.get("location_preference", "").lower()
            in (required_location or "").lower()
        ):
            score += 5

        deadline_str = email.get("deadline")
        if deadline_str is not None:
            try:
                days_left = (
                    datetime.strptime(deadline_str, "%Y-%m-%d").date() - date.today()
                ).days
                if days_left < 0:
                    score += 0
                elif days_left <= 7:
                    score += 30
                elif days_left <= 14:
                    score += 20
                elif days_left <= 30:
                    score += 10
            except ValueError:
                print(
                    f"Malformed date for email {email.get('filename', 'N/A')}: {deadline_str}"
                )
                pass

        required_docs = set(d.lower() for d in email.get("required_documents", []))
        available_docs = set(
            d.lower() for d in student_profile.get("available_documents", [])
        )
        if not required_docs:
            score += 10
        else:
            doc_ratio = len(available_docs & required_docs) / len(required_docs)
            score += round(doc_ratio * 10)

        ranked_emails.append([email, score])
    return ranked_emails


def explain_emails(student_profile, ranked_emails):
    output_emails = []
    for opportunity_with_score in ranked_emails:
        opportunity_to_explain = opportunity_with_score[0]
        score = opportunity_with_score[1]

        formatted_explanation_prompt = EXPLANATION_PROMPT.format(
            student_profile=json.dumps(student_profile, indent=2),
            ranked_opportunities_json=json.dumps(opportunity_to_explain, indent=2),
        )
        explanation_response_content = get_llm_response(
            formatted_explanation_prompt, ""
        )
        output_emails.append([explanation_response_content, score])
    return output_emails


def get_llm_response(prompt, user_input):
    conversation = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_input},
    ]

    response = llm.invoke(conversation)
    return response.content  # Return only the content string


if __name__ == "__main__":
    pass
