import re
from typing import Tuple

ACTION_VERBS = [
    'achieved', 'improved', 'pioneered', 'managed', 'created', 'developed', 'led', 'increased', 'decreased',
    'negotiated', 'launched', 'won', 'optimized', 'overhauled', 'restructured', 'spearheaded', 'transformed',
    'accelerated', 'delivered', 'established', 'implemented', 'produced', 'resolved', 'revitalized'
]

COMMON_SECTIONS = ['experience', 'education', 'skills', 'projects', 'summary', 'objective', 'contact']

def calculate_ats_score(resume_text: str) -> Tuple[int, str]:
    text = (resume_text or '').lower()
    score = 0
    analysis_breakdown = []

    # 1. Contact Information (20)
    has_email = bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', text))
    has_phone = bool(re.search(r'(\+\d{1,3}[- ]?)?\d{10}', text))
    contact_score = 20 if (has_email and has_phone) else 10 if (has_email or has_phone) else 0
    analysis_breakdown.append(f"Contact Information ({contact_score}/20): {'Contains email and phone' if contact_score==20 else 'Partial or missing contact info'}")
    score += contact_score

    # 2. Action Verbs (30)
    words = re.findall(r"\w+", text)
    found_verbs = set(w for w in words if w in ACTION_VERBS)
    action_verb_score = min(30, len(found_verbs) * 3)
    analysis_breakdown.append(f"Action Verbs ({action_verb_score}/30): Found {len(found_verbs)} strong verbs.")
    score += action_verb_score

    # 3. Quantifiable Results (30)
    quantifiable_metrics = re.findall(r"(\d+%|\$\d+|\d+ million|\d+ billion|team of \d+)", text)
    quantifiable_score = min(30, len(quantifiable_metrics) * 6)
    analysis_breakdown.append(f"Quantifiable Results ({quantifiable_score}/30): Found {len(quantifiable_metrics)} measurable metrics.")
    score += quantifiable_score

    # 4. Structure (20)
    found_sections = [s for s in COMMON_SECTIONS if s in text]
    structure_score = min(20, len(found_sections) * 4)
    analysis_breakdown.append(f"Structure ({structure_score}/20): Found sections: {', '.join(found_sections) if found_sections else 'none'}.")
    score += structure_score

    analysis = '\n\n'.join(analysis_breakdown)
    return score, analysis


# Simple skills extraction: keyword matching with optional years parsing
SKILLS_LIST = [
    'python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'sql', 'postgres', 'mysql', 'aws', 'azure',
    'docker', 'kubernetes', 'flask', 'django', 'react', 'angular', 'vue', 'html', 'css', 'git', 'redis',
    'mongodb', 'graphql', 'rest', 'node', 'express', 'spring', 'tensorflow', 'pytorch', 'pandas', 'numpy'
]

def extract_skills(resume_text: str):
    text = (resume_text or '').lower()
    found = []
    for skill in SKILLS_LIST:
        if skill in text:
            # try to find an adjacent "X years" mention for this skill
            years = None
            try:
                # look for patterns like "3 years of Python" or "Python (3 years)"
                import re
                # pattern after skill: "skill .* (\d+)\s+years"
                pat_after = re.compile(rf"{skill}.{{0,40}}?(\d+)\s+years")
                m = pat_after.search(text)
                if m:
                    years = int(m.group(1))
                else:
                    # pattern before skill: "(\d+) years .* skill"
                    pat_before = re.compile(rf"(\d+)\s+years?.{{0,40}}?{skill}")
                    m2 = pat_before.search(text)
                    if m2:
                        years = int(m2.group(1))
            except Exception:
                years = None
            entry = {'skill': skill}
            if years:
                entry['years'] = years
            found.append(entry)
    return found
