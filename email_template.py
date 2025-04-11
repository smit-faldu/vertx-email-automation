import concurrent.futures
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers.json import parse_json_markdown
import re
import os
from dotenv import load_dotenv
load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Define the shared model and parser
model = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=GEMINI_API_KEY, temperature=0.5)
parser = JsonOutputParser()

def build_prompt(variant, founder_data):
    descriptions = {
        "Custom": "Craft an email with a personalized touch. Highlight unique aspects of the company and the founder's journey...",
        "Business": "Develop a formal, business-focused email. Emphasize traction, opportunity, financials...",
        "Personal": "Share the founder's personal journey and vision behind the company...",
        "Metrics": (
            "Write a professional email focused on key performance indicators and traction metrics. "
            "Avoid repeating the subject in the body. Do not use markdown. Format numbers cleanly, "
            "and avoid placeholders like [Insert Market Size]. Keep the tone business-focused. "
            "Return only subject and body in JSON format."
        ),
        "Vision": "Inspire the investor by sharing long-term vision and mission..."
    }

    prompt = PromptTemplate(
        template=f"""You are an expert email copywriter for founders talking to investors.

Generate a single email in the **{variant}** style as described below:
{descriptions[variant]}

Use this founder and company info:
1. Founder Name: {founder_data.get("founder_name", "")}
2. What are you building? {founder_data.get("what_building", "")}
3. Co-builders? {founder_data.get("co_builders", "")}
4. Contact: {founder_data.get("best_contact", "")}
5. Product link: {founder_data.get("product_link", "")}
6. Presence: {founder_data.get("professional_presence", "")}
7. Industry: {founder_data.get("industry", "")}
8. Company Name: {founder_data.get("company_name", "")}
9. Description: {founder_data.get("description", "")}
10. Sectors: {founder_data.get("sectors", "")}
11. Traction: {founder_data.get("traction", "")}
12. Required funding: {founder_data.get("required_funding", "")}
13. Previous funding: {founder_data.get("previous_funding", "")}
14. Target countries: {founder_data.get("target_countries", "")}
15. Product stage: {founder_data.get("product_stage", "")}

Return JSON like:

  "subject": "Subject line here",
  "body": "Body content here"
""",
        input_variables=[]
    )
    return prompt

def clean_body(body, subject):
    lines = body.strip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        first_line = lines[0][8:].strip()
        if subject.lower().strip() in first_line.lower():
            return "\n".join(lines[1:]).strip()
    return body.strip()


# def call_model(prompt):
#     chain = prompt | model | parser
#     return chain.invoke({})  # Nothing to pass since we bake founder_data directly into prompt

def call_model(prompt):
    chain = prompt | model
    raw_output = chain.invoke({})
    
    # try:
    #     result = parser.invoke(raw_output)
    # except Exception:
    #     try:
    #         result = parse_json_markdown(raw_output)
    #     except Exception as e:
    #         return {"subject": "Error", "body": f"Invalid JSON output:\n\n{raw_output}"}

    # # Remove "Subject:" prefix in body if it repeats
    # subject = result.get("subject", "")
    # body = result.get("body", "")
    # result["body"] = clean_body(body, subject)

    # return result
    try:
        result = parser.invoke(raw_output)
    except Exception:
        try:
            result = parse_json_markdown(raw_output)
        except Exception:
            return {
                "subject": "Error",
                "body": f"Invalid JSON output:\n\n{raw_output}"
            }

    subject = result.get("subject", "")
    body = result.get("body", "")
    
    return result

def generate_email_variants(founder_data):
    variants = ["Custom", "Business", "Personal", "Metrics", "Vision"]
    results = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            variant: executor.submit(call_model, build_prompt(variant, founder_data))
            for variant in variants
        }

        for variant, future in futures.items():
            try:
                result = future.result(timeout=30)
                results[variant] = result
            except Exception as e:
                print(f"[Error: {variant}] {e}")
                results[variant] = {"subject": "Error", "body": str(e)}
                
    print("Emial_templet",results,"\n\n")

    return results