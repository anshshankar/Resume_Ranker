from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List,Dict, Union
import json
from json import JSONDecodeError
from openai import OpenAI
import os
import PyPDF2
from docx import Document
from io import BytesIO
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = FastAPI(title="Resume Ranking API", version="1.0.0")

class ExtractCriteriaResponse(BaseModel):
    criteria: List[str]


def parse_criteria(criteria_input: Union[str, Dict, ExtractCriteriaResponse]) -> List[str]:
    try:
        if isinstance(criteria_input, str):
            parsed = json.loads(criteria_input)
            if isinstance(parsed, dict) and "criteria" in parsed:
                return parsed["criteria"]
            raise ValueError("JSON must contain a 'criteria' key with an array value")
            
        elif isinstance(criteria_input, dict):
            if "criteria" in criteria_input:
                return criteria_input["criteria"]
            raise ValueError("Dictionary must contain a 'criteria' key with an array value")
            
        elif isinstance(criteria_input, ExtractCriteriaResponse):
            return criteria_input.criteria
            
        else:
            raise ValueError("Unsupported criteria format")
            
    except JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing criteria: {str(e)}")

def extract_text_from_file(file: UploadFile) -> str:
    content = file.file.read()
    if file.filename.endswith('.pdf'):
        pdf_reader = PyPDF2.PdfReader(BytesIO(content))
        text = ''.join([page.extract_text() for page in pdf_reader.pages])
    elif file.filename.endswith('.docx'):
        doc = Document(BytesIO(content))
        text = '\n'.join([para.text for para in doc.paragraphs])
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are allowed.")
    return text

@app.post("/extract-criteria", response_model=ExtractCriteriaResponse, summary="Extract ranking criteria from job description")
async def extract_criteria(file: UploadFile = File(..., description="Job description file (PDF or DOCX)")):
    try:
        text = extract_text_from_file(file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Analyze the job description and extract only the essential criteria that directly help evaluate candidate qualifications. Focus on:

                    1. Required and preferred qualifications:
                    - Educational requirements
                    - Years of experience
                    - Technical skills and proficiencies
                    - Certifications and licenses
                    - Domain expertise
                    - Required languages (programming or spoken)

                    2. Measurable competencies:
                    - Specific tools or technologies
                    - Performance metrics
                    - Leadership experience (number of direct reports, budget size)
                    - Project scale indicators

                    Ignore:
                    - Generic soft skills (unless specifically quantified)
                    - Company culture statements
                    - Basic job responsibilities
                    - Benefits and perks
                    - Location requirements (unless specialized)

                    Format each criterion as a clear, actionable statement.

                    Return a JSON object with a 'criteria' array containing the extracted criteria as strings."""},
                
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        criteria = result.get('criteria', [])
        if not isinstance(criteria, list):
            criteria = []
        return {"criteria": criteria}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

def evaluate_resume(text: str, criteria: List[str]) -> Dict:
    prompt = f"""
    Evaluate the following resume against the given criteria. For each criterion:
    - Assign a score from 0-5 where:
      0: No relevant experience/qualification
      1: Minimal match
      3: Meets expectations
      5: Exceeds expectations
    - Consider both explicit mentions and implied experience
    - Extract the candidate's name from the resume
    
    Resume:
    {text}
    
    Criteria to evaluate:
    {json.dumps(criteria, indent=2)}
    
    Return a JSON object with:
    1. "name": Candidate's full name (or "Unknown" if not found)
    2. "scores": Dictionary mapping each criterion to its score (0-5)
    3. "explanations": Brief explanation for each score
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert resume evaluator."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise ValueError(f"Error evaluating resume: {str(e)}")

@app.post("/score-resumes")
async def score_resumes(
    criteria: Union[str, Dict, ExtractCriteriaResponse] = Form(..., description="Ranking criteria as JSON string or object"),
    files: List[UploadFile] = File(..., description="Resume files (PDF or DOCX)"),
):
    try:
        criteria_list = parse_criteria(criteria)
        if not criteria_list:
            raise HTTPException(status_code=400, detail="At least one criterion is required")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not files:
        raise HTTPException(status_code=400, detail="At least one resume file is required")
        
    for file in files:
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format for {file.filename}. Only PDF and DOCX files are accepted."
            )
    
    rows = []
    errors = []
    
    for file in files:
        try:
            text = extract_text_from_file(file)

            result = evaluate_resume(text, criteria_list)

            row = {
                "Filename": file.filename,
                "Candidate Name": result.get('name', 'Unknown')
            }

            scores = result.get('scores', {})
            explanations = result.get('explanations', {})
            
            for criterion in criteria_list:
                row[f"{criterion} (Score)"] = scores.get(criterion, 0)
                row[f"{criterion} (Explanation)"] = explanations.get(criterion, "No explanation provided")

            row["Total Score"] = sum(scores.values())
            row["Average Score"] = round(sum(scores.values()) / len(criteria_list), 2)
            
            rows.append(row)
            
        except Exception as e:
            errors.append(f"Error processing {file.filename}: {str(e)}")
            continue
    
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No resumes could be processed successfully. Errors: " + "; ".join(errors)
        )
    
    df = pd.DataFrame(rows)
    
    score_cols = [col for col in df.columns if "Score" in col]
    explanation_cols = [col for col in df.columns if "Explanation" in col]
    base_cols = ["Filename", "Candidate Name"]
    
    df = df[base_cols + score_cols + explanation_cols]

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Resume Scores', index=False)

        worksheet = writer.sheets['Resume Scores']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            worksheet.set_column(idx, idx, max_length + 2)
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=resume_scores_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)