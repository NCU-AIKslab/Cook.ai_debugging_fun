"""
Evaluation Formatters for Quality Critic Results

This module provides formatters to transform raw evaluation results
into different formats for different consumers:
- Revise Agent: Action-oriented revision instructions
- Metrics/Analytics: Statistical data for experiments
- Frontend: Minimal data for UI rendering
"""

from typing import Dict, List, Any


class EvaluationFormatter:
    """Formatter for Quality Critic evaluation results."""
    
    @staticmethod
    def for_revise_agent(evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format evaluation for revise agent.
        
        Returns action-oriented revision instructions focused on:
        - Which items (overall exam or specific questions) need revision
        - What problems were identified
        - How to fix them (specific actions)
        
        Args:
            evaluation: Raw evaluation result from QualityCritic
            
        Returns:
            Dict with revision_required, failed_criteria_summary, revision_instructions
        """
        overall_evals = evaluation.get("overall", {}).get("evaluations", [])
        mode = evaluation.get("mode", "quick")
        
        # Determine if revision is required
        failed_overall = [e for e in overall_evals if e.get("rating", 0) < 4.0]
        revision_required = len(failed_overall) > 0
        
        # Build revision instructions
        revision_instructions = []
        
        # Overall exam issues
        if failed_overall:
            overall_issues = []
            for eval_item in failed_overall:
                overall_issues.append({
                    "criterion": eval_item["criteria"],
                    "problem": eval_item.get("analysis", "未達標準"),
                    "action": " | ".join(eval_item.get("suggestions", ["請改進"]))
                })
            
            revision_instructions.append({
                "target": "overall",
                "issues": overall_issues
            })
        
        # Per-question issues (comprehensive mode only)
        if mode == "comprehensive":
            per_question = evaluation.get("per_question", [])
            for question_eval in per_question:
                question_type = question_eval.get("question_type", "unknown")
                question_num = question_eval.get("question_number")
                failed_evals = [e for e in question_eval.get("evaluations", []) 
                              if e.get("rating", 0) < 4.0]
                
                if failed_evals:
                    question_issues = []
                    for eval_item in failed_evals:
                        question_issues.append({
                            "criterion": eval_item["criteria"],
                            "problem": eval_item.get("analysis", "未達標準"),
                            "action": " | ".join(eval_item.get("suggestions", ["請改進"]))
                        })
                    
                    revision_instructions.append({
                        "target": f"question_{question_num}",
                        "question_type": question_type,
                        "question_number": question_num,
                        "issues": question_issues
                    })
        
        return {
            "revision_required": revision_required,
            "failed_criteria_summary": [e["criteria"] for e in failed_overall],
            "revision_instructions": revision_instructions
        }
    
    @staticmethod
    def for_metrics(evaluation: Dict[str, Any], duration_ms: int, num_questions: int) -> Dict[str, Any]:
        """
        Format evaluation for data analysis and experiments.
        
        Returns pure statistical data without text descriptions:
        - Scores by criterion
        - Pass/fail status
        - Performance metrics
        
        Args:
            evaluation: Raw evaluation result from QualityCritic
            duration_ms: Evaluation duration in milliseconds
            num_questions: Number of questions evaluated
            
        Returns:
            Dict with statistical metrics
        """
        overall_evals = evaluation.get("overall", {}).get("evaluations", [])
        mode = evaluation.get("mode", "quick")
        
        # Calculate overall scores
        overall_scores = {e["criteria"]: e["rating"] for e in overall_evals}
        avg_score = sum(overall_scores.values()) / len(overall_scores) if overall_scores else 0
        failed_criteria = [e["criteria"] for e in overall_evals if e["rating"] < 4.0]
        is_passed = len(failed_criteria) == 0
        
        metrics = {
            "mode": mode,
            "is_passed": is_passed,
            "threshold": 4.0,
            "num_questions": num_questions,
            "duration_ms": duration_ms,
            "scores": {
                "overall": overall_scores,
                "avg": round(avg_score, 2)
            },
            "failed_criteria": failed_criteria
        }
        
        # Add per-question metrics for comprehensive mode
        if mode == "comprehensive":
            per_question = evaluation.get("per_question", [])
            
            # Calculate pass rate by criterion
            criterion_names = list(overall_scores.keys())
            pass_rate_by_criterion = {}
            
            for criterion in criterion_names:
                passed_count = sum(
                    1 for q in per_question
                    for e in q.get("evaluations", [])
                    if e["criteria"] == criterion and e.get("rating", 0) >= 4.0
                )
                total_count = len(per_question)
                pass_rate_by_criterion[criterion] = round(passed_count / total_count, 2) if total_count > 0 else 0
            
            metrics["pass_rate_by_criterion"] = pass_rate_by_criterion
            
            # Per-question scores
            metrics["per_question_scores"] = [
                {
                    "question_type": q.get("question_type", "unknown"),
                    "question_number": q["question_number"],
                    "scores": {e["criteria"]: e["rating"] for e in q.get("evaluations", [])},
                    "avg_score": round(
                        sum(e["rating"] for e in q.get("evaluations", [])) / len(q.get("evaluations", []))
                        if q.get("evaluations") else 0,
                        2
                    )
                }
                for q in per_question
            ]
            
            # Statistics summary
            stats = evaluation.get("statistics", {})
            if stats:
                metrics["statistics"] = {
                    "avg_score_per_question": stats.get("avg_score_per_question"),
                    "min_score": stats.get("min_score"),
                    "max_score": stats.get("max_score")
                }
        
        return metrics
    
    @staticmethod
    def for_frontend(evaluation: Dict[str, Any], num_questions: int) -> Dict[str, Any]:
        """
        Format evaluation for frontend rendering.
        
        Returns minimal data needed for UI display:
        - Pass/fail status
        - Summary information
        - Evaluation details by criterion
        
        Args:
            evaluation: Raw evaluation result from QualityCritic
            num_questions: Number of questions evaluated
            
        Returns:
            Dict with minimal frontend data
        """
        overall_evals = evaluation.get("overall", {}).get("evaluations", [])
        mode = evaluation.get("mode", "quick")
        
        failed_criteria = [e["criteria"] for e in overall_evals if e["rating"] < 4.0]
        is_passed = len(failed_criteria) == 0
        
        response = {
            "is_passed": is_passed,
            "summary": {
                "failed_criteria": failed_criteria,
                "num_questions": num_questions,
                "mode": mode
            },
            "overall_evaluation": [
                {
                    "criterion": e["criteria"],
                    "rating": e["rating"],
                    "threshold": 4.0,
                    "analysis": e.get("analysis", ""),
                    "suggestions": e.get("suggestions", [])
                }
                for e in overall_evals
            ]
        }
        
        # Add per-question evaluation for comprehensive mode
        if mode == "comprehensive":
            response["per_question_evaluation"] = [
                {
                    "question_type": q.get("question_type", "unknown"),
                    "question_number": q["question_number"],
                    "evaluations": [
                        {
                            "criterion": e["criteria"],
                            "rating": e["rating"],
                            "analysis": e.get("analysis", ""),
                            "suggestions": e.get("suggestions", [])
                        }
                        for e in q.get("evaluations", [])
                    ]
                }
                for q in evaluation.get("per_question", [])
            ]
        
        return response
