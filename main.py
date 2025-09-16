import streamlit as st
import google.generativeai as genai
# import pytesseract
# from PIL import Image
import io
import pdfplumber
import os

# Set page config
st.set_page_config(page_title="AI Mock Interview", page_icon="🤖", layout="wide")

# Configure Gemini (user needs to set their API key)
@st.cache_resource
def configure_gemini(api_key):
    if not api_key:
        st.error("Please enter a valid Gemini API Key to proceed. The app uses this for generating questions and evaluations.")
        st.info("Note: Using the app will consume your API quota/credits. Gemini 2.0 Flash is free for light usage, but check Google's pricing.")
        st.stop()
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    return model

# Function to extract text from resume (PDF or image)
def extract_resume_text(uploaded_file):
    if uploaded_file is not None:
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                text = ""
                for page in pdf.pages:
                    extracted_text = page.extract_text()
                    if extracted_text:
                        text += extracted_text + "\n"
            if not text.strip():
                st.error("No text could be extracted from the PDF. Please ensure it's a text-based PDF.")
                return ""
            return text.strip()
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return ""
    return ""

# Function to generate questions using Gemini
def generate_questions(model, resume_text, role, num_questions):
    prompt = f"""
    Based on the following resume:
    {resume_text}
    
    For the role of {role}, generate exactly {num_questions} interview questions.
    Mix technical and behavioral questions (aim for 60% technical, 40% behavioral).
    Number them 1 to {num_questions}.
    For each question, provide a brief expected key points in evaluation (hidden for user, but include for later eval).
    Format as:
    Question 1: [Question text]
    Expected: [brief key points]
    
    ... and so on.
    """
    response = model.generate_content(prompt)
    return response.text

# Function to evaluate answers using Gemini
def evaluate_answers(model, questions_with_expected, answers, resume_text, role):
    formatted_qa = ""
    for i, (q, expected) in enumerate(questions_with_expected, 1):
        ans = answers.get(i, "")
        formatted_qa += f"Question {i}: {q}\nExpected key points: {expected}\nAnswer: {ans}\n\n"
    
    prompt = f"""
    Evaluate the following Q&A for the role of {role} based on resume:
    {resume_text}
    
    {formatted_qa}
    
    Provide:
    - Overall score out of 10.
    - Score per question out of 10.
    - Strengths.
    - Areas for improvement with specific suggestions.
    - General feedback.
    
    Be constructive and detailed.
    """
    response = model.generate_content(prompt)
    return response.text

# Main app
def main():
    st.title("🤖 AI Mock Interview")
    st.markdown("Upload your resume, select a role, and get personalized interview questions!")

    # Step 0: Get API key from user or secrets/env
    st.sidebar.header("API Key Required")
    api_key = st.sidebar.text_input(
        "Enter your Google Gemini API Key (get one at https://aistudio.google.com/app/apikey):",
        type="password",
        value=st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    )

    model = configure_gemini(api_key)

    # Step 1: Upload resume
    uploaded_file = st.file_uploader("Upload your resume (PDF Only)", type=['pdf'])
    resume_text = ""
    if uploaded_file:
        with st.spinner("Extracting text from resume..."):
            resume_text = extract_resume_text(uploaded_file)
        if resume_text:
            st.success("Resume text extracted successfully!")
            st.text_area("Extracted Resume Text (preview):", value=resume_text[:1000] + "..." if len(resume_text) > 1000 else resume_text, height=200, disabled=True)
        else:
            st.error("Could not extract text from resume. Please ensure it's readable.")
            st.stop()

    # Step 2: Select role
    roles = ["React Developer", "Backend Developer", "Full Stack Developer", "Data Scientist", "Product Manager"]
    selected_role = st.selectbox("Select the role you're targeting:", roles)

    # Step 3: Number of questions
    num_questions = st.slider("Number of questions (technical + behavioral):", min_value=3, max_value=10, value=5)

    # Generate questions button
    if st.button("Generate Questions") and resume_text:
        with st.spinner("Generating questions..."):
            questions_text = generate_questions(model, resume_text, selected_role, num_questions)
            st.session_state.questions_text = questions_text
            st.session_state.questions = []  # Reset
            st.rerun()

    # Display questions and answer fields
    if 'questions_text' in st.session_state:
        st.subheader("Interview Questions")
        # Parse questions (simple parsing assuming format)
        lines = st.session_state.questions_text.split('\n')
        questions_with_expected = []
        current_q = ""
        current_exp = ""
        q_num = 1
        for line in lines:
            if line.startswith("Question "):
                if current_q:
                    questions_with_expected.append((current_q, current_exp))
                current_q = line.split(":", 1)[1].strip()
                current_exp = ""
            elif line.startswith("Expected:"):
                current_exp = line.split(":", 1)[1].strip()
            elif line.strip() and not line.startswith("Question ") and not line.startswith("Expected:"):
                current_q += " " + line.strip()
        
        if current_q:
            questions_with_expected.append((current_q, current_exp))

        # Limit to num_questions
        questions_with_expected = questions_with_expected[:num_questions]

        # Store questions for display
        st.session_state.questions = [q for q, _ in questions_with_expected]
        st.session_state.expected = [e for _, e in questions_with_expected]

        # Answer text areas
        answers = {}
        for i, question in enumerate(st.session_state.questions, 1):
            st.markdown(f"**Question {i}:** {question}")
            ans = st.text_area(f"Answer {i}", key=f"ans_{i}", height=100)
            answers[i] = ans

        # Submit for evaluation
        if st.button("Submit Answers for Evaluation"):
            if all(answers.values()):  # Check if all answered
                with st.spinner("Evaluating answers..."):
                    eval_result = evaluate_answers(model, list(zip(st.session_state.questions, st.session_state.expected)), answers, resume_text, selected_role)
                    st.session_state.eval_result = eval_result
                    st.rerun()
            else:
                st.warning("Please answer all questions before submitting.")

        # Display evaluation
        if 'eval_result' in st.session_state:
            st.subheader("Evaluation & Feedback")
            st.markdown(st.session_state.eval_result)

if __name__ == "__main__":
    main()