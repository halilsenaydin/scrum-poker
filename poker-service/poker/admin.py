from collections import Counter, defaultdict
from datetime import datetime
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import statistics
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Room, Participant, Task, TaskVote
from .services import RoomService

class RoomAdminExcel():
    def _sheet_rooms(self, wb, rooms):
        ws = wb.active
        ws.title = "Rooms"

        headers = ["room_code", "name", "is_active", "revealed", "created_at", "participant_count", "task_count"]
        ws.append(headers)
        self._style_header(ws)

        for r in rooms:
            ws.append([
                r.room_code, 
                r.name, 
                r.is_active, 
                r.revealed,
                r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                r.get_participant_count(),
                r.tasks.filter(is_active=True).count()
            ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_participants(self, wb, rooms):
        ws = wb.create_sheet("Participants")
        ws.append(["room_code", "participant", "is_active", "total_votes"])
        self._style_header(ws)

        for r in rooms:
            for p in r.participants.all():
                ws.append([
                    r.room_code, 
                    p.name, 
                    p.is_active,
                    p.votes.count()
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_tasks(self, wb, rooms):
        ws = wb.create_sheet("Tasks")
        ws.append([
            "room_code", "task_id", "title", "description", 
            "sp", "status", "is_active", "vote_count", "created_at"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                ws.append([
                    r.room_code, 
                    t.id, 
                    t.title, 
                    t.description, 
                    t.sp, 
                    t.status, 
                    t.is_active,
                    t.get_vote_count(),
                    t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else ""
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_votes(self, wb, rooms):
        ws = wb.create_sheet("Votes")
        ws.append(["room_code", "task_id", "task_title", "participant", "vote", "voted_at", "is_numeric"])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                for v in t.votes.select_related("participant"):
                    ws.append([
                        r.room_code, 
                        t.id, 
                        t.title,
                        v.participant.name, 
                        v.vote,
                        v.voted_at.strftime("%Y-%m-%d %H:%M:%S") if v.voted_at else "",
                        v.is_numeric()
                    ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_consensus(self, wb, rooms):
        ws = wb.create_sheet("Consensus")
        ws.append([
            "room_code", "task_id", "task_title", "total_votes",
            "avg", "median", "min", "max", "std_dev", "consensus_score"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                votes = []
                for v in t.votes.all():
                    try:
                        votes.append(float(v.vote))
                    except:
                        pass

                if len(votes) < 1:
                    continue

                avg = round(statistics.mean(votes), 2)
                median = statistics.median(votes)
                std = round(statistics.stdev(votes), 2) if len(votes) > 1 else 0
                consensus = max(0, 100 - (std * 10))

                ws.append([
                    r.room_code, 
                    t.id, 
                    t.title,
                    len(votes),
                    avg, 
                    median,
                    min(votes),
                    max(votes),
                    std, 
                    round(consensus, 2)
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_task_participant_matrix(self, wb, rooms):
        ws = wb.create_sheet("Task_Participant_Matrix")
        
        for r in rooms:
            # Get all participants for this room
            participants = list(r.participants.all().order_by('name'))
            
            if not participants:
                continue
            
            # Add room separator
            if ws.max_row > 1:
                ws.append([])  # Empty row as separator
                ws.append([])  # Empty row as separator
            
            # Room header
            room_header_row = ws.max_row + 1
            ws.append([f"ROOM: {r.name} ({r.room_code})"])
            ws.merge_cells(f'A{room_header_row}:{get_column_letter(len(participants) + 1)}{room_header_row}')
            ws[f'A{room_header_row}'].font = Font(bold=True, size=12, color="FFFFFF")
            ws[f'A{room_header_row}'].fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            ws[f'A{room_header_row}'].alignment = Alignment(horizontal='center')
            
            # Column headers: Task Name + Participant names
            header_row = ['Task Name'] + [p.name for p in participants]
            ws.append(header_row)
            
            # Style header row
            header_row_num = ws.max_row
            for col_num, cell in enumerate(ws[header_row_num], 1):
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            
            # Get all tasks for this room
            tasks = r.tasks.all().order_by('-created_at')
            
            for task in tasks:
                # Create a row for each task
                row_data = [task.title]
                
                # Get votes for each participant
                for participant in participants:
                    vote = task.get_participant_vote(participant)
                    if vote:
                        row_data.append(vote.vote)
                    else:
                        row_data.append('')  # No vote
                
                ws.append(row_data)
                
                # Style the data row
                current_row = ws.max_row
                for col_num in range(1, len(row_data) + 1):
                    cell = ws.cell(row=current_row, column=col_num)
                    cell.border = Border(
                        left=Side(style='thin', color='CCCCCC'),
                        right=Side(style='thin', color='CCCCCC'),
                        top=Side(style='thin', color='CCCCCC'),
                        bottom=Side(style='thin', color='CCCCCC')
                    )
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    
                    # Color code votes if numeric
                    if col_num > 1 and cell.value:
                        try:
                            vote_value = float(cell.value)
                            # Color coding based on vote value
                            if vote_value <= 3:
                                cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                            elif vote_value <= 5:
                                cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                            elif vote_value <= 8:
                                cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                            else:
                                cell.fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                        except (ValueError, TypeError):
                            # Non-numeric vote
                            cell.fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
        
        # Auto-adjust column widths
        self._auto_adjust_column_width(ws)
        
        # Set minimum width for task name column
        ws.column_dimensions['A'].width = max(ws.column_dimensions['A'].width, 30)

    def _sheet_pivot_room_summary(self, wb, rooms):
        ws = wb.create_sheet("Pivot_Room_Summary")
        
        ws.append([
            "room_code", "room_name", "total_participants", "active_participants",
            "total_tasks", "active_tasks", "completed_tasks", "total_votes",
            "avg_consensus", "avg_vote_value", "high_risk_tasks", "medium_risk_tasks", "low_risk_tasks"
        ])
        self._style_header(ws)

        for r in rooms:
            active_participants = r.get_active_participants().count()
            all_participants = r.participants.count()
            
            tasks = r.tasks.all()
            active_tasks = tasks.filter(is_active=True)
            completed_tasks = tasks.filter(status='completed')
            
            total_votes = sum(t.get_vote_count() for t in tasks)
            
            consensus_scores = []
            vote_values = []
            risk_distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            
            for t in tasks:
                if t.metrics and 'consensus_score' in t.metrics:
                    consensus_scores.append(t.metrics['consensus_score'])
                    
                    score = t.metrics['consensus_score']
                    if score >= 80:
                        risk_distribution["LOW"] += 1
                    elif score >= 50:
                        risk_distribution["MEDIUM"] += 1
                    else:
                        risk_distribution["HIGH"] += 1
                
                if t.metrics and 'average' in t.metrics:
                    vote_values.append(t.metrics['average'])
            
            avg_consensus = round(statistics.mean(consensus_scores), 2) if consensus_scores else 0
            avg_vote = round(statistics.mean(vote_values), 2) if vote_values else 0
            
            ws.append([
                r.room_code,
                r.name,
                all_participants,
                active_participants,
                tasks.count(),
                active_tasks.count(),
                completed_tasks.count(),
                total_votes,
                avg_consensus,
                avg_vote,
                risk_distribution["HIGH"],
                risk_distribution["MEDIUM"],
                risk_distribution["LOW"]
            ])
        
        self._auto_adjust_column_width(ws)
        self._add_conditional_formatting_consensus(ws, 'I')

    def _sheet_pivot_participant_activity(self, wb, rooms):
        ws = wb.create_sheet("Pivot_Participant_Activity")
        
        ws.append([
            "room_code", "participant", "total_votes", "avg_vote_value",
            "most_common_vote", "vote_variance", "tasks_participated"
        ])
        self._style_header(ws)

        for r in rooms:
            for p in r.participants.all():
                votes = p.votes.all()
                
                if not votes:
                    continue
                
                numeric_votes = []
                vote_values = []
                
                for v in votes:
                    vote_values.append(v.vote)
                    try:
                        numeric_votes.append(float(v.vote))
                    except:
                        pass
                
                avg_vote = round(statistics.mean(numeric_votes), 2) if numeric_votes else 0
                most_common = Counter(vote_values).most_common(1)[0][0] if vote_values else "N/A"
                variance = round(statistics.variance(numeric_votes), 2) if len(numeric_votes) > 1 else 0
                
                ws.append([
                    r.room_code,
                    p.name,
                    votes.count(),
                    avg_vote,
                    most_common,
                    variance,
                    len(set(v.task_id for v in votes))
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_pivot_task_complexity(self, wb, rooms):
        ws = wb.create_sheet("Pivot_Task_Complexity")
        
        ws.append([
            "room_code", "task_id", "task_title", "vote_count", "avg_vote",
            "std_dev", "coefficient_of_variation", "consensus_score", "complexity_level"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                votes = []
                for v in t.votes.all():
                    try:
                        votes.append(float(v.vote))
                    except:
                        pass
                
                if not votes:
                    continue
                
                avg = statistics.mean(votes)
                std = statistics.stdev(votes) if len(votes) > 1 else 0
                cv = (std / avg * 100) if avg > 0 else 0
                consensus = max(0, 100 - (std * 10))
                
                # Complexity level based on average vote and variance
                if avg <= 3 and cv < 30:
                    complexity = "SIMPLE"
                elif avg <= 5 and cv < 50:
                    complexity = "MODERATE"
                elif avg <= 8:
                    complexity = "COMPLEX"
                else:
                    complexity = "VERY_COMPLEX"
                
                ws.append([
                    r.room_code,
                    t.id,
                    t.title,
                    len(votes),
                    round(avg, 2),
                    round(std, 2),
                    round(cv, 2),
                    round(consensus, 2),
                    complexity
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_vote_distribution_analysis(self, wb, rooms):
        ws = wb.create_sheet("Vote_Distribution")
        
        ws.append([
            "room_code", "task_id", "vote_value", "count", "percentage"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                if not t.metrics or 'distribution' not in t.metrics:
                    continue
                
                distribution = t.metrics['distribution']
                total = sum(distribution.values())
                
                for vote_value, count in sorted(distribution.items()):
                    percentage = round((count / total * 100), 2) if total > 0 else 0
                    
                    ws.append([
                        r.room_code,
                        t.id,
                        vote_value,
                        count,
                        percentage
                    ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_time_series_analysis(self, wb, rooms):
        ws = wb.create_sheet("Time_Series_Analysis")
        
        ws.append([
            "room_code", "date", "hour", "total_votes", "unique_participants",
            "unique_tasks", "avg_consensus"
        ])
        self._style_header(ws)

        vote_data = defaultdict(lambda: {
            'votes': 0, 
            'participants': set(), 
            'tasks': set(),
            'consensus_scores': []
        })

        for r in rooms:
            for t in r.tasks.all():
                for v in t.votes.all():
                    if not v.voted_at:
                        continue
                    
                    date_key = v.voted_at.strftime("%Y-%m-%d")
                    hour_key = v.voted_at.hour
                    key = (r.room_code, date_key, hour_key)
                    
                    vote_data[key]['votes'] += 1
                    vote_data[key]['participants'].add(v.participant_id)
                    vote_data[key]['tasks'].add(t.id)
                    
                    if t.metrics and 'consensus_score' in t.metrics:
                        vote_data[key]['consensus_scores'].append(t.metrics['consensus_score'])

        for (room_code, date, hour), data in sorted(vote_data.items()):
            avg_consensus = round(statistics.mean(data['consensus_scores']), 2) if data['consensus_scores'] else 0
            
            ws.append([
                room_code,
                date,
                hour,
                data['votes'],
                len(data['participants']),
                len(data['tasks']),
                avg_consensus
            ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_participant_agreement_matrix(self, wb, rooms):
        ws = wb.create_sheet("Participant_Agreement")
        
        ws.append([
            "room_code", "participant_1", "participant_2", 
            "common_tasks", "agreement_rate", "avg_vote_diff"
        ])
        self._style_header(ws)

        for r in rooms:
            participants = list(r.participants.all())
            
            for i, p1 in enumerate(participants):
                for p2 in participants[i+1:]:
                    # Find common tasks
                    p1_votes = {v.task_id: v.vote for v in p1.votes.all()}
                    p2_votes = {v.task_id: v.vote for v in p2.votes.all()}
                    
                    common_tasks = set(p1_votes.keys()) & set(p2_votes.keys())
                    
                    if not common_tasks:
                        continue
                    
                    agreements = 0
                    vote_diffs = []
                    
                    for task_id in common_tasks:
                        v1 = p1_votes[task_id]
                        v2 = p2_votes[task_id]
                        
                        if v1 == v2:
                            agreements += 1
                        
                        try:
                            diff = abs(float(v1) - float(v2))
                            vote_diffs.append(diff)
                        except:
                            pass
                    
                    agreement_rate = round((agreements / len(common_tasks) * 100), 2)
                    avg_diff = round(statistics.mean(vote_diffs), 2) if vote_diffs else 0
                    
                    ws.append([
                        r.room_code,
                        p1.name,
                        p2.name,
                        len(common_tasks),
                        agreement_rate,
                        avg_diff
                    ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_outlier_detection(self, wb, rooms):
        ws = wb.create_sheet("Outlier_Detection")
        
        ws.append([
            "room_code", "task_id", "task_title", "participant", 
            "vote", "task_avg", "deviation", "is_outlier"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                votes = []
                vote_map = {}
                
                for v in t.votes.all():
                    try:
                        vote_value = float(v.vote)
                        votes.append(vote_value)
                        vote_map[v.participant.name] = (v.vote, vote_value)
                    except:
                        pass
                
                if len(votes) < 3:
                    continue
                
                avg = statistics.mean(votes)
                std = statistics.stdev(votes)
                
                for participant_name, (original_vote, vote_value) in vote_map.items():
                    deviation = abs(vote_value - avg)
                    is_outlier = deviation > (2 * std) if std > 0 else False
                    
                    ws.append([
                        r.room_code,
                        t.id,
                        t.title,
                        participant_name,
                        original_vote,
                        round(avg, 2),
                        round(deviation, 2),
                        "YES" if is_outlier else "NO"
                    ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_ai_training_dataset(self, wb, rooms):
        ws = wb.create_sheet("AI_Training_Dataset")
        
        ws.append([
            "room_code", "task_id", "participant_count", "vote_count",
            "avg_vote", "median_vote", "min_vote", "max_vote", "vote_range",
            "std_dev", "variance", "coefficient_of_variation",
            "consensus_score", "has_outliers", "vote_diversity_index",
            "risk_level", "complexity_level"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                votes = []
                for v in t.votes.all():
                    try:
                        votes.append(float(v.vote))
                    except:
                        pass
                
                if not votes:
                    continue
                
                participant_count = r.get_active_participants().count()
                vote_count = len(votes)
                
                avg = statistics.mean(votes)
                median = statistics.median(votes)
                min_vote = min(votes)
                max_vote = max(votes)
                vote_range = max_vote - min_vote
                std = statistics.stdev(votes) if len(votes) > 1 else 0
                variance = statistics.variance(votes) if len(votes) > 1 else 0
                cv = (std / avg * 100) if avg > 0 else 0
                consensus = max(0, 100 - (std * 10))
                
                # Outlier detection
                has_outliers = any(abs(v - avg) > (2 * std) for v in votes) if std > 0 else False
                
                # Vote diversity (Shannon entropy-like)
                vote_counter = Counter(votes)
                total = len(votes)
                diversity = -sum((count/total) * (count/total) for count in vote_counter.values())
                
                # Risk level
                if consensus >= 80:
                    risk = "LOW"
                elif consensus >= 50:
                    risk = "MEDIUM"
                else:
                    risk = "HIGH"
                
                # Complexity
                if avg <= 3 and cv < 30:
                    complexity = "SIMPLE"
                elif avg <= 5 and cv < 50:
                    complexity = "MODERATE"
                elif avg <= 8:
                    complexity = "COMPLEX"
                else:
                    complexity = "VERY_COMPLEX"
                
                ws.append([
                    r.room_code,
                    t.id,
                    participant_count,
                    vote_count,
                    round(avg, 2),
                    round(median, 2),
                    round(min_vote, 2),
                    round(max_vote, 2),
                    round(vote_range, 2),
                    round(std, 2),
                    round(variance, 2),
                    round(cv, 2),
                    round(consensus, 2),
                    "YES" if has_outliers else "NO",
                    round(diversity, 4),
                    risk,
                    complexity
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_risk_assessment(self, wb, rooms):
        ws = wb.create_sheet("Risk_Assessment")
        
        ws.append([
            "room_code", "task_id", "task_title", "risk_level",
            "risk_score", "consensus_score", "vote_spread", "outlier_count",
            "recommendation"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                votes = []
                for v in t.votes.all():
                    try:
                        votes.append(float(v.vote))
                    except:
                        pass
                
                if not votes:
                    continue
                
                avg = statistics.mean(votes)
                std = statistics.stdev(votes) if len(votes) > 1 else 0
                consensus = max(0, 100 - (std * 10))
                vote_spread = max(votes) - min(votes)
                
                # Count outliers
                outlier_count = sum(1 for v in votes if abs(v - avg) > (2 * std)) if std > 0 else 0
                
                # Calculate risk score (0-100, higher = more risky)
                risk_score = 0
                risk_score += (100 - consensus) * 0.4  # Consensus weight
                risk_score += min(vote_spread * 5, 40)  # Spread weight
                risk_score += min(outlier_count * 10, 20)  # Outlier weight
                
                if risk_score >= 70:
                    risk_level = "HIGH"
                    recommendation = "Re-discuss task; significant disagreement detected"
                elif risk_score >= 40:
                    risk_level = "MEDIUM"
                    recommendation = "Review outliers; consider brief clarification"
                else:
                    risk_level = "LOW"
                    recommendation = "Proceed with estimation"
                
                ws.append([
                    r.room_code,
                    t.id,
                    t.title,
                    risk_level,
                    round(risk_score, 2),
                    round(consensus, 2),
                    round(vote_spread, 2),
                    outlier_count,
                    recommendation
                ])
        
        self._auto_adjust_column_width(ws)
        self._add_conditional_formatting_risk(ws, 'D')

    def _sheet_estimation_accuracy(self, wb, rooms):
        ws = wb.create_sheet("Estimation_Accuracy")
        
        ws.append([
            "room_code", "task_id", "task_title", "estimated_sp",
            "avg_vote", "final_sp", "estimation_diff", "accuracy_rate"
        ])
        self._style_header(ws)

        for r in rooms:
            for t in r.tasks.all():
                if not t.sp:
                    continue
                
                votes = []
                for v in t.votes.all():
                    try:
                        votes.append(float(v.vote))
                    except:
                        pass
                
                if not votes:
                    continue
                
                avg_vote = statistics.mean(votes)
                estimation_diff = abs(t.sp - avg_vote)
                accuracy_rate = 100 - min((estimation_diff / t.sp * 100), 100) if t.sp > 0 else 0
                
                ws.append([
                    r.room_code,
                    t.id,
                    t.title,
                    t.sp,
                    round(avg_vote, 2),
                    t.sp,
                    round(estimation_diff, 2),
                    round(accuracy_rate, 2)
                ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_team_dynamics(self, wb, rooms):
        ws = wb.create_sheet("Team_Dynamics")
        
        ws.append([
            "room_code", "total_participants", "active_participants",
            "avg_participation_rate", "avg_agreement_rate", "team_cohesion_score",
            "dominant_voter", "most_diverse_voter"
        ])
        self._style_header(ws)

        for r in rooms:
            total_participants = r.participants.count()
            active_participants = r.get_active_participants().count()
            
            if active_participants == 0:
                continue
            
            tasks = r.tasks.all()
            participation_rates = []
            agreement_rates = []
            
            participant_vote_counts = defaultdict(int)
            participant_variance = {}
            
            for t in tasks:
                task_votes = t.get_vote_count()
                if active_participants > 0:
                    participation_rates.append((task_votes / active_participants) * 100)
                
                # Count votes per participant
                for v in t.votes.all():
                    participant_vote_counts[v.participant.name] += 1
            
            # Calculate variance for each participant
            for p in r.participants.all():
                numeric_votes = []
                for v in p.votes.all():
                    try:
                        numeric_votes.append(float(v.vote))
                    except:
                        pass
                
                if len(numeric_votes) > 1:
                    participant_variance[p.name] = statistics.variance(numeric_votes)
            
            avg_participation = round(statistics.mean(participation_rates), 2) if participation_rates else 0
            
            # Team cohesion (based on consensus scores)
            consensus_scores = []
            for t in tasks:
                if t.metrics and 'consensus_score' in t.metrics:
                    consensus_scores.append(t.metrics['consensus_score'])
            
            team_cohesion = round(statistics.mean(consensus_scores), 2) if consensus_scores else 0
            
            dominant_voter = max(participant_vote_counts, key=participant_vote_counts.get) if participant_vote_counts else "N/A"
            most_diverse = max(participant_variance, key=participant_variance.get) if participant_variance else "N/A"
            
            ws.append([
                r.room_code,
                total_participants,
                active_participants,
                avg_participation,
                0,  # Placeholder for agreement rate
                team_cohesion,
                dominant_voter,
                most_diverse
            ])
        
        self._auto_adjust_column_width(ws)

    def _sheet_executive_summary(self, wb, rooms):
        ws = wb.create_sheet("Executive_Summary")
        
        # Title
        ws.merge_cells('A1:F1')
        ws['A1'] = "SCRUM POKER - EXECUTIVE SUMMARY"
        ws['A1'].font = Font(bold=True, size=16)
        ws['A1'].alignment = Alignment(horizontal='center')
        
        row = 3
        
        # Overall statistics
        ws[f'A{row}'] = "OVERALL STATISTICS"
        ws[f'A{row}'].font = Font(bold=True, size=14)
        row += 1
        
        total_rooms = rooms.count()
        total_participants = sum(r.participants.count() for r in rooms)
        total_tasks = sum(r.tasks.count() for r in rooms)
        total_votes = sum(sum(t.get_vote_count() for t in r.tasks.all()) for r in rooms)
        
        ws[f'A{row}'] = "Total Rooms:"
        ws[f'B{row}'] = total_rooms
        row += 1
        
        ws[f'A{row}'] = "Total Participants:"
        ws[f'B{row}'] = total_participants
        row += 1
        
        ws[f'A{row}'] = "Total Tasks:"
        ws[f'B{row}'] = total_tasks
        row += 1
        
        ws[f'A{row}'] = "Total Votes:"
        ws[f'B{row}'] = total_votes
        row += 2
        
        # Consensus Analysis
        ws[f'A{row}'] = "CONSENSUS ANALYSIS"
        ws[f'A{row}'].font = Font(bold=True, size=14)
        row += 1
        
        all_consensus_scores = []
        risk_distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        for r in rooms:
            for t in r.tasks.all():
                if t.metrics and 'consensus_score' in t.metrics:
                    score = t.metrics['consensus_score']
                    all_consensus_scores.append(score)
                    
                    if score >= 80:
                        risk_distribution["LOW"] += 1
                    elif score >= 50:
                        risk_distribution["MEDIUM"] += 1
                    else:
                        risk_distribution["HIGH"] += 1
        
        if all_consensus_scores:
            ws[f'A{row}'] = "Average Consensus Score:"
            ws[f'B{row}'] = round(statistics.mean(all_consensus_scores), 2)
            row += 1
            
            ws[f'A{row}'] = "High Consensus Tasks (>80%):"
            ws[f'B{row}'] = risk_distribution["LOW"]
            row += 1
            
            ws[f'A{row}'] = "Medium Consensus Tasks (50-80%):"
            ws[f'B{row}'] = risk_distribution["MEDIUM"]
            row += 1
            
            ws[f'A{row}'] = "Low Consensus Tasks (<50%):"
            ws[f'B{row}'] = risk_distribution["HIGH"]
            row += 2
        
        # Top performers
        ws[f'A{row}'] = "TOP INSIGHTS"
        ws[f'A{row}'].font = Font(bold=True, size=14)
        row += 1
        
        ws[f'A{row}'] = "Most Active Room:"
        most_active_room = max(rooms, key=lambda r: sum(t.get_vote_count() for t in r.tasks.all()), default=None)
        ws[f'B{row}'] = most_active_room.name if most_active_room else "N/A"
        row += 1
        
        ws[f'A{row}'] = "Highest Consensus Room:"
        room_consensus = {}
        for r in rooms:
            scores = []
            for t in r.tasks.all():
                if t.metrics and 'consensus_score' in t.metrics:
                    scores.append(t.metrics['consensus_score'])
            if scores:
                room_consensus[r.name] = statistics.mean(scores)
        
        if room_consensus:
            best_room = max(room_consensus, key=room_consensus.get)
            ws[f'B{row}'] = f"{best_room} ({round(room_consensus[best_room], 2)}%)"
        else:
            ws[f'B{row}'] = "N/A"
        
        self._auto_adjust_column_width(ws)

    def _add_consensus_charts(self, wb, rooms):
        if "Consensus" not in wb.sheetnames:
            return
        
        ws = wb["Consensus"]
        
        if ws.max_row <= 1:
            return
        
        # Create a chart for each room
        for room_idx, room in enumerate(rooms):
            # Find rows for this room in the Consensus sheet
            room_rows = []
            for row_idx in range(2, ws.max_row + 1):
                if ws.cell(row=row_idx, column=1).value == room.room_code:
                    room_rows.append(row_idx)
            
            if not room_rows:
                continue
            
            # Create bar chart for consensus scores
            chart = BarChart()
            chart.title = f"Consensus Scores - {room.name} ({room.room_code})"
            chart.y_axis.title = "Consensus Score (%)"
            chart.x_axis.title = "Tasks"
            chart.height = 10
            chart.width = 20
            
            # Add data (consensus_score column is column 10)
            min_row = min(room_rows)
            max_row = max(room_rows)
            
            data = Reference(ws, min_col=10, min_row=min_row, max_row=max_row)
            categories = Reference(ws, min_col=3, min_row=min_row, max_row=max_row)
            
            chart.add_data(data, titles_from_data=False)
            chart.set_categories(categories)
            
            # Position chart
            ws.add_chart(chart, "L2")

    def _add_vote_distribution_charts(self, wb, rooms):
        if "Vote_Distribution" not in wb.sheetnames:
            return
        
        ws = wb["Vote_Distribution"]
        
        if ws.max_row <= 1:
            return
        
        # Create charts for each room showing overall vote distribution
        for room in rooms:
            # Aggregate all votes for this room
            vote_aggregation = {}
            
            for task in room.tasks.all():
                if task.metrics and 'distribution' in task.metrics:
                    for vote_value, count in task.metrics['distribution'].items():
                        if vote_value in vote_aggregation:
                            vote_aggregation[vote_value] += count
                        else:
                            vote_aggregation[vote_value] = count
            
            if not vote_aggregation:
                continue
            
            # Write aggregated data to a temporary area in the sheet
            temp_start_row = ws.max_row + 5
            ws.cell(row=temp_start_row, column=1).value = "Vote Value"
            ws.cell(row=temp_start_row, column=2).value = "Count"
            
            current_row = temp_start_row + 1
            for vote_value, count in sorted(vote_aggregation.items()):
                ws.cell(row=current_row, column=1).value = str(vote_value)
                ws.cell(row=current_row, column=2).value = count
                current_row += 1
            
            # Create pie chart
            chart = PieChart()
            chart.title = f"Vote Distribution - {room.name}"
            chart.height = 10
            chart.width = 12
            
            data = Reference(ws, min_col=2, min_row=temp_start_row, max_row=current_row - 1)
            categories = Reference(ws, min_col=1, min_row=temp_start_row + 1, max_row=current_row - 1)
            
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)

        ws.add_chart(chart, "G2")

    def _style_header(self, ws):
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

    def _auto_adjust_column_width(self, ws):
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _add_conditional_formatting_consensus(self, ws, column):
        last_row = ws.max_row
        if last_row > 1:
            ws.conditional_formatting.add(
                f'{column}2:{column}{last_row}',
                ColorScaleRule(
                    start_type='num', start_value=0, start_color='F8696B',
                    mid_type='num', mid_value=50, mid_color='FFEB84',
                    end_type='num', end_value=100, end_color='63BE7B'
                )
            )

    def _add_conditional_formatting_risk(self, ws, column):
        last_row = ws.max_row
        
        for row in range(2, last_row + 1):
            cell = ws[f'{column}{row}']
            if cell.value == "HIGH":
                cell.fill = PatternFill(start_color='F8696B', end_color='F8696B', fill_type='solid')
            elif cell.value == "MEDIUM":
                cell.fill = PatternFill(start_color='FFEB84', end_color='FFEB84', fill_type='solid')
            elif cell.value == "LOW":
                cell.fill = PatternFill(start_color='63BE7B', end_color='63BE7B', fill_type='solid')

    def _bold(self, ws):
        for cell in ws[1]:
            cell.font = Font(bold=True)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin, RoomAdminExcel):
    list_display = [
        'room_code', 
        'name', 
        'participant_count', 
        'task_count', 
        'vote_count',
        'avg_consensus',
        'revealed', 
        'is_active', 
        'created_at'
    ]
    list_filter = ['is_active', 'revealed', 'created_at']
    search_fields = ['name', 'room_code']
    readonly_fields = ['room_code', 'created_at']
    fieldsets = (
        (_('admin_room_fieldset_base_info_label'), {
            'fields': ('name', 'room_code', 'room_password', 'revealed'),
        }),
        (_('admin_room_fieldset_time_info_label'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    actions = [
        'reveal_all_votes', 
        'reset_all_votes', 
        'deactivate_rooms', 
        'export_rooms_full_excel',
        'export_advanced_analytics'
    ]
    room_service = RoomService()

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['room_code', 'created_at', 'room_password']
        return ['room_code', 'created_at']

    def participant_count(self, obj):
        count = obj.get_participant_count()
        if count > 0:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', count)
        return format_html('<span style="color: gray;">0</span>')
    participant_count.short_description = _('admin_room_participant_label')
    
    def task_count(self, obj):
        count = obj.tasks.filter(is_active=True).count()
        if count > 0:
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>', count)
        return format_html('<span style="color: gray;">0</span>')
    task_count.short_description = _('admin_room_task_label')

    def vote_count(self, obj):
        """Total vote count across all tasks"""
        count = sum(task.get_vote_count() for task in obj.tasks.filter(is_active=True))
        if count > 0:
            return format_html('<span style="color: purple; font-weight: bold;">{}</span>', count)
        return format_html('<span style="color: gray;">0</span>')
    vote_count.short_description = _('Total Votes')

    def avg_consensus(self, obj):
        """Average consensus score across all tasks"""
        tasks = obj.tasks.filter(is_active=True)
        consensus_scores = []
        
        for task in tasks:
            if task.metrics and 'consensus_score' in task.metrics:
                consensus_scores.append(task.metrics['consensus_score'])
        
        if consensus_scores:
            avg = round(statistics.mean(consensus_scores), 1)
            color = 'green' if avg >= 80 else 'orange' if avg >= 50 else 'red'
            return format_html('<span style="color: {}; font-weight: bold;">{}%</span>', color, avg)
        return format_html('<span style="color: gray;">-</span>')
    avg_consensus.short_description = _('Avg Consensus')
    
    def reveal_all_votes(self, request, queryset):
        for room in queryset:
            room.reveal_votes()
        self.message_user(request, f"{queryset.count()} {_('admin_room_action_revealed')}")
    reveal_all_votes.short_description = _('admin_room_action_reveal_votes')
    
    def reset_all_votes(self, request, queryset):
        for room in queryset:
            room.reset_votes()
        self.message_user(request, f"{queryset.count()} {_('admin_room_action_reset')}")
    reset_all_votes.short_description = _('admin_room_action_reset_votes')
    
    def deactivate_rooms(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} {_('admin_room_action_deactivate')}")
    deactivate_rooms.short_description = _('admin_room_action_deactivate_rooms')

    def export_advanced_analytics(self, request, queryset):
        wb = Workbook()

        # Basic data sheets
        self._sheet_rooms(wb, queryset)
        self._sheet_participants(wb, queryset)
        self._sheet_tasks(wb, queryset)
        self._sheet_votes(wb, queryset)
        self._sheet_consensus(wb, queryset)
        
        # Advanced analytics sheets
        self._sheet_task_participant_matrix(wb, queryset)
        self._sheet_pivot_room_summary(wb, queryset)
        self._sheet_pivot_participant_activity(wb, queryset)
        self._sheet_pivot_task_complexity(wb, queryset)
        self._sheet_vote_distribution_analysis(wb, queryset)
        self._sheet_time_series_analysis(wb, queryset)
        self._sheet_participant_agreement_matrix(wb, queryset)
        self._sheet_outlier_detection(wb, queryset)
        self._sheet_ai_training_dataset(wb, queryset)
        self._sheet_risk_assessment(wb, queryset)
        self._sheet_estimation_accuracy(wb, queryset)
        self._sheet_team_dynamics(wb, queryset)
        self._sheet_executive_summary(wb, queryset)

        # Add charts
        self._add_consensus_charts(wb, queryset)
        self._add_vote_distribution_charts(wb, queryset)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="scrum_poker_advanced_analytics_{timestamp}.xlsx"'

        wb.save(response)
        return response

    export_advanced_analytics.short_description = _("Export Advanced Analytics (Excel)")

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['name', 'room_code', 'vote_count', 'is_active']
    list_filter = ['is_active', 'room']
    search_fields = ['name', 'room__room_code', 'authentication_key']
    readonly_fields = ['authentication_key']
    
    fieldsets = (
        (_('admin_participant_fieldset_base_info_label'), {
            'fields': ('room', 'name', 'authentication_key')
        }),
    )

    def has_add_permission(self, _):
        return False
    
    def room_code(self, obj):
        return obj.room.room_code
    room_code.short_description = _('admin_participant_room_code_label')
    room_code.admin_order_field = 'room__room_code'
    
    def vote_count(self, obj):
        count = obj.votes.count()
        if count > 0:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', count)
        return format_html('<span style="color: gray;">0</span>')
    vote_count.short_description = _('admin_participant_vote_count_label')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'room_code', 'sp', 'status', 'vote_count', 'consensus_indicator', 'is_active', 'created_at']
    list_filter = ['status', 'is_active', 'created_at', 'room']
    search_fields = ['title', 'description', 'room__room_code']
    readonly_fields = ['metrics', 'created_at', 'updated_at', 'metrics_display']
    
    fieldsets = (
        (_('admin_task_fieldset_base_info_label'), {
            'fields': ('room', 'title', 'description')
        }),
        (_('admin_task_fieldset_estimate_info_label'), {
            'fields': ('sp', 'status', 'metrics_display')
        }),
        (_('admin_task_fieldset_time_info_label'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        (_('admin_task_fieldset_technical_info_label'), {
            'fields': ('metrics',),
            'classes': ('collapse',)
        }),
    )
    
    def room_code(self, obj):
        return obj.room.room_code
    room_code.short_description = _('admin_task_room_code_label')
    room_code.admin_order_field = 'room__room_code'
    
    def vote_count(self, obj):
        count = obj.get_vote_count()
        total = obj.room.get_participant_count()
        
        if total > 0:
            percentage = (count / total) * 100
            color = 'green' if percentage == 100 else 'orange' if percentage >= 50 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}/{} ({}%)</span>',
                color, count, total, int(percentage)
            )
        return format_html('<span style="color: gray;">{}/0</span>', count)
    vote_count.short_description = _('admin_task_vote_count_label')
    
    def consensus_indicator(self, obj):
        if not obj.metrics or 'consensus_score' not in obj.metrics:
            return format_html('<span style="color: gray;">-</span>')
        
        score = obj.metrics['consensus_score']
        if score >= 80:
            color = 'green'
            icon = '✓'
        elif score >= 50:
            color = 'orange'
            icon = '~'
        else:
            color = 'red'
            icon = '✗'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}%</span>',
            color, icon, int(score)
        )
    consensus_indicator.short_description = _('admin_task_consensus_label')
    
    def metrics_display(self, obj):
        if not obj.metrics:
            return format_html('<span style="color: gray;">{}</span>', _("admin_task_metrics_no_votes"))
        
        html = '<table style="border-collapse: collapse;">'
        
        metrics_map = {
            'total_votes': _('admin_task_metrics_total_votes'),
            'average': _('admin_task_metrics_average'),
            'median': _('admin_task_metrics_median'),
            'min': _('admin_task_metrics_min'),
            'max': _('admin_task_metrics_max'),
            'std_dev': _('admin_task_metrics_std_dev'),
            'consensus_score': _('admin_task_metrics_consensus_score'),
        }
        
        for key, label in metrics_map.items():
            if key in obj.metrics:
                value = obj.metrics[key]
                html += f'<tr><td style="padding: 4px 8px; font-weight: bold;">{label}:</td><td style="padding: 4px 8px;">{value}</td></tr>'
        
        if 'distribution' in obj.metrics:
            html += f'<tr><td style="padding: 4px 8px; font-weight: bold;">{_("admin_task_metrics_distribution")}:</td><td style="padding: 4px 8px;">'
            for vote_val, count in sorted(obj.metrics['distribution'].items()):
                html += f'{vote_val}: {count} {_("admin_task_metrics_vote")}<br>'
            html += '</td></tr>'
        
        html += '</table>'
        return format_html(html)
    metrics_display.short_description = _('admin_task_metrics_display_label')
    
    actions = ['recalculate_metrics', 'reset_task_votes']
    
    def recalculate_metrics(self, request, queryset):
        for task in queryset:
            task.calculate_metrics()
            task.save()
        self.message_user(request, f"{queryset.count()} {_('admin_task_recalculated_metrics')}")
    recalculate_metrics.short_description = _('admin_task_action_recalculate_metrics')
    
    def reset_task_votes(self, request, queryset):
        for task in queryset:
            task.reset_votes()
        self.message_user(request, f"{queryset.count()} {_('admin_task_reset_task_votes')}")
    reset_task_votes.short_description = _('admin_task_action_reset_task_votes')


@admin.register(TaskVote)
class TaskVoteAdmin(admin.ModelAdmin):
    list_display = ['participant_name', 'task_title', 'vote', 'is_numeric_vote', 'voted_at']
    list_filter = ['voted_at', 'vote', 'task__room']
    search_fields = ['participant__name', 'task__title', 'vote']
    readonly_fields = ['voted_at']
    fieldsets = (
        (_('admin_task_vote_fieldset_vote_info_label'), {
            'fields': ('task', 'participant', 'vote')
        }),
        (_('admin_task_vote_fieldset_time_info_label'), {
            'fields': ('voted_at',),
            'classes': ('collapse',)
        }),
    )
    
    def participant_name(self, obj):
        return obj.participant.name
    participant_name.short_description = _('admin_task_vote_participant_name_label')
    participant_name.admin_order_field = 'participant__name'
    
    def task_title(self, obj):
        return obj.task.title[:50] + '...' if len(obj.task.title) > 50 else obj.task.title
    task_title.short_description = _('admin_task_vote_task_title_label')
    task_title.admin_order_field = 'task__title'
    
    def is_numeric_vote(self, obj):
        if obj.is_numeric():
            return format_html('<span style="color: green;">✓ {}</span>', _('admin_task_vote_numeric_vote'))
        return format_html('<span style="color: orange;">{} ({0})</span>', _('admin_task_vote_custom_vote'), obj.vote)
    is_numeric_vote.short_description = _('admin_task_vote_is_numeric_vote_label')
