# Resume Ranking API

A FastAPI-based application that automates the process of ranking resumes based on job descriptions. The API provides endpoints to extract ranking criteria from job descriptions and score multiple resumes against these criteria.

## Features

- Extract ranking criteria from job descriptions (PDF/DOCX)
- Score multiple resumes against specified criteria
- Support for PDF and DOCX file formats
- Automated scoring on a 0-5 scale
- Excel report generation with detailed scoring breakdown
- OpenAI GPT-4 powered analysis
- Interactive Swagger UI documentation

## Prerequisites

- Python 3.8+
- OpenAI API key
- Virtual environment (recommended)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/anshshankar/Resume_Ranker.git
cd Project_Directory
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Running the Application

1. Start the FastAPI server:
```bash
uvicorn main:app --reload
```

2. Access the API documentation:
- Swagger UI: http://localhost:8000/docs

## API Endpoints

### 1. Extract Criteria from Job Description
```http
POST /extract-criteria
```
Extracts ranking criteria from a job description file.

**Input:**
- `file`: Job description document (PDF/DOCX)

**Output:**
```json
{
  "criteria": [
    "Must have certification XYZ",
    "5+ years of experience in Python development",
    "Strong background in Machine Learning"
  ]
}
```

### 2. Score Resumes
```http
POST /score-resumes
```
Scores multiple resumes against provided criteria.

**Input:**
- `criteria`: JSON string or object containing ranking criteria
- `files`: List of resume files (PDF/DOCX)

**Output:**
- Excel file containing:
  - Candidate names
  - Individual criterion scores (0-5)
  - Score explanations
  - Total and average scores

## Example Usage

Using Python requests:

```python
import requests

# Extract criteria
with open('job_description.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/extract-criteria',
        files={'file': f}
    )
criteria = response.json()

# Score resumes
files = [
    ('files', open('resume1.pdf', 'rb')),
    ('files', open('resume2.pdf', 'rb'))
]
response = requests.post(
    'http://localhost:8000/score-resumes',
    data={'criteria': json.dumps(criteria)},
    files=files
)
```

## Error Handling

The API includes comprehensive error handling for:
- Invalid file formats
- Missing or malformed criteria
- File processing errors
- OpenAI API errors

All errors return appropriate HTTP status codes and descriptive error messages.

## Development

The project uses:
- FastAPI for the web framework
- OpenAI GPT-4o mini for text analysis
- PyPDF2 and python-docx for file processing
- pandas and xlsxwriter for report generation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request