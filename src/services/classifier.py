import re
import json
from typing import List, Dict, Optional
from src.services.llm import get_llm_client, LLM_MODEL

DOC_CATEGORIES = [
    "Lecture Notes",
    "Syllabus",
    "Previous Year Questions",
    "Lab Manual",
    "Reference Book"
]

def sanitize_text(text: str) -> str:
    """Removes null bytes and malformed characters."""
    if not text:
        return ""
    return text.replace("\x00", "").replace("\u0000", "")

def classify_document_and_subject(
    sample_text: str,
    filename: str,
    available_courses: List[Dict[str, str]]
) -> Dict[str, str]:
    """
    Predicts course_id and doc_type based on filename, text preview,
    and the list of enrolled/registered courses.
    """
    clean_sample = sanitize_text(sample_text[:2500])
    combined_probe = (filename + " " + clean_sample).lower()

    # 1. Deterministic Course Matching
    detected_course = None
    for course in available_courses:
        code = course["code"].upper()
        title = course.get("title", "").lower()
        if code.lower() in combined_probe:
            detected_course = code
            break
        if title and len(title) > 3 and title in combined_probe:
            detected_course = code
            break

    # 2. Deterministic Doc Type Matching
    detected_type = None
    if re.search(r"\b(syllabus|curriculum|scheme|course\s+outcomes?)\b", combined_probe):
        detected_type = "Syllabus"
    elif re.search(r"\b(pyq|exam|midsem|endsem|question\s+paper|max(?:imum)?\s+marks?)\b", combined_probe):
        detected_type = "Previous Year Questions"
    elif re.search(r"\b(lab|manual|experiment|practical|apparatus)\b", combined_probe):
        detected_type = "Lab Manual"
    elif re.search(r"\b(lecture|chapter|unit\s+\d+|module\s+\d+|notes?)\b", combined_probe):
        detected_type = "Lecture Notes"

    # If heuristics found both, return directly without LLM latency
    default_course = available_courses[0]["code"] if available_courses else "CSE1001"
    if detected_course and detected_type:
        return {
            "course_id": detected_course,
            "doc_type": detected_type,
            "confidence": "high"
        }

    # 3. LLM Fallback (Groq) for Ambiguous Documents
    try:
        client = get_llm_client()
        course_list_str = ", ".join([f"{c['code']} ({c.get('title', '')})" for c in available_courses])
        
        system_prompt = (
            "You are an academic document parser. Classify the document's Subject Code and Document Type.\n"
            f"Available Courses: [{course_list_str}]\n"
            f"Allowed Doc Types: {DOC_CATEGORIES}\n\n"
            "Return strictly valid JSON with keys 'course_id' and 'doc_type'. Nothing else."
        )

        user_content = f"Filename: {filename}\nExcerpt:\n\"\"\"\n{clean_sample[:1500]}\n\"\"\""

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        parsed = json.loads(response.choices[0].message.content)
        predicted_course = parsed.get("course_id", "").strip().upper()
        predicted_type = parsed.get("doc_type", "").strip()

        # Validate against allowed course codes
        valid_codes = [c["code"].upper() for c in available_courses]
        final_course = predicted_course if predicted_course in valid_codes else (detected_course or default_course)
        
        # Validate doc type
        final_type = detected_type or "Lecture Notes"
        for cat in DOC_CATEGORIES:
            if cat.lower() in predicted_type.lower():
                final_type = cat
                break

        return {
            "course_id": final_course,
            "doc_type": final_type,
            "confidence": "llm"
        }
    except Exception as e:
        print(f"[CLASSIFIER ERROR] LLM fallback exception: {e}")
        return {
            "course_id": detected_course or default_course,
            "doc_type": detected_type or "Lecture Notes",
            "confidence": "fallback"
        }