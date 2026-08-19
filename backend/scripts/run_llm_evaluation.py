import os
import sys
import json
import csv
import time
from typing import List, Dict

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.rag_chain import rag_chain_service
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.app.config.settings import settings

QUESTIONS_FILE = r"C:\Users\uday raj nkashyap\.gemini\antigravity-ide\brain\91a90878-b576-42b6-99bd-2b2c8bbbb011\scratch\generated_questions.json"
OUTPUT_CSV = "rag_llm_evaluation.csv"
EVALUATOR_MODEL = "gemini-3.6-flash"

# Evaluation Prompt
EVAL_PROMPT = """
You are an expert evaluator for a Retrieval-Augmented Generation (RAG) system.
You will be given a Question, the Generated Answer, and the Retrieved Contexts (chunks).
Your task is to evaluate the system's performance based on Relevancy, Precision, Recall, and Correctness.

Question: {question}

Generated Answer: {answer}

Retrieved Contexts:
{contexts}

Please evaluate and provide your scores in EXACTLY the following JSON format without any markdown blocks or other text:
{{
    "faithfulness": <float between 0 and 1, representing the extent to which the generated answer is faithful to and supported by the retrieved contexts>,
    "recall_at_k": <float between 0 and 1, representing the extent to which the retrieved contexts contain all the necessary information to fully answer the question>,
    "correctness": <int between 1 and 10, rating how accurate and correct the generated answer is based on the question and context>
}}
"""

def main():
    if not os.path.exists(QUESTIONS_FILE):
        print(f"Questions file not found: {QUESTIONS_FILE}")
        return

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions_data = json.load(f)
    
    print(f"Loaded {len(questions_data)} questions.")
    
    print("Initializing RAG pipeline...")
    rag_chain_service.initialize()
    print("Pipeline initialized.")

    if not settings.GOOGLE_API_KEY:
        print("GOOGLE_API_KEY is not set. Cannot run LLM evaluator.")
        return

    evaluator_llm = ChatGoogleGenerativeAI(
        model=EVALUATOR_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.0,
        max_retries=1
    )
    eval_chain = ChatPromptTemplate.from_template(EVAL_PROMPT) | evaluator_llm | StrOutputParser()

    results = []
    
    for i, item in enumerate(questions_data, start=1):
        paper = item["paper"]
        question = item["question"]
        print(f"\n[{i}/{len(questions_data)}] Paper: {paper}")
        print(f"Question: {question}")

        start_time = time.time()
        # Query the RAG pipeline
        response_obj = rag_chain_service.invoke(question)
        rag_latency = time.time() - start_time
        
        answer = response_obj.get("answer", "")
        contexts = response_obj.get("contexts", [])
        
        contexts_text = ""
        for idx, ctx in enumerate(contexts):
            contexts_text += f"--- Chunk {idx+1} ---\n{ctx}\n\n"
            
        print(f"Retrieved {len(contexts)} chunks. Latency: {rag_latency:.2f}s")
        
        # Call the Evaluator LLM
        eval_result = {}
        try:
            eval_response = eval_chain.invoke({
                "question": question,
                "answer": answer,
                "contexts": contexts_text if contexts_text else "None"
            })
            
            eval_response = eval_response.strip()

            import re
            json_match = re.search(r'\{.*\}', eval_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = eval_response
                
            eval_result = json.loads(json_str)
            
            faithfulness = float(eval_result.get("faithfulness", 0.0))
            recall = float(eval_result.get("recall_at_k", 0.0))
            correctness = float(eval_result.get("correctness", 0.0))
            feedback = eval_result.get("feedback", "")
            print(f"Scores -> Faithfulness: {faithfulness}, Recall@{len(contexts)}: {recall}, Correctness: {correctness}")
        except Exception as e:
            print(f"Evaluation failed for this question: {e}")
 
            if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                print("Model not found. Trying fallback 'gemini-2.5-flash'...")
                fallback_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.0
                )
                eval_chain = ChatPromptTemplate.from_template(EVAL_PROMPT) | fallback_llm | StrOutputParser()
                try:
                    eval_response = eval_chain.invoke({
                        "question": question,
                        "answer": answer,
                        "contexts": contexts_text if contexts_text else "None"
                    })
                    
                    json_match = re.search(r'\{.*\}', eval_response, re.DOTALL)
                    json_str = json_match.group(0) if json_match else eval_response
                        
                    eval_result = json.loads(json_str)
                    faithfulness = float(eval_result.get("faithfulness", 0.0))
                    recall = float(eval_result.get("recall_at_k", 0.0))
                    correctness = float(eval_result.get("correctness", 0.0))
                    feedback = eval_result.get("feedback", "")
                    print(f"Scores (Fallback) -> Faithfulness: {faithfulness}, Recall@{len(contexts)}: {recall}, Correctness: {correctness}")
                except Exception as fallback_e:
                    print(f"Fallback evaluation also failed: {fallback_e}")
                    faithfulness, recall, correctness, feedback = 0.0, 0.0, 0.0, f"Error: {str(e)}"
            else:
                safe_resp = eval_response.encode('ascii', 'replace').decode('ascii') if 'eval_response' in locals() else 'None'
                print(f"Raw output was: {safe_resp}")
                faithfulness, recall, correctness, feedback = 0.0, 0.0, 0.0, f"Error: {str(e)}"
            
        results.append({
            "paper": paper,
            "question": question,
            "answer": answer,
            "k_chunks_retrieved": len(contexts),
            "faithfulness": faithfulness,
            "recall_at_k": recall,
            "correctness": correctness,
            "feedback": feedback,
            "latency_sec": round(rag_latency, 2)
        })
        
        print("Waiting 30 seconds to respect API rate limits...")
        time.sleep(15)

    # Save to CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nEvaluation complete. Results saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
