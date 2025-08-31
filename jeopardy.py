#!/usr/bin/env python3
import json
import random

# Path to your JSON file
FILE_PATH = "JEOPARDY_QUESTIONS1.json"

def load_questions(file_path):
    """Load questions from the JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_random_jeopardy_question():
    if not jeopardy_questions:
        return None
    # Ensure it's a dict
    q = random.choice(jeopardy_questions)
    if isinstance(q, dict):
        return q
    else:
        # If the JSON contains strings, wrap it in a dict with 'question' key
        return {"category": "Unknown", "value": "N/A", "question": str(q), "answer": "Answer not available"}


def main():
    questions = load_questions(FILE_PATH)
    question = get_random_question(questions)
    
    # Print the question in a readable way
    print("Category:", question.get("category", "Unknown"))
    print("Value:", question.get("value", "N/A"))
    print("Question:", question.get("question", "No question text"))
    print("Answer:", question.get("answer", "No answer provided"))

if __name__ == "__main__":
    main()
