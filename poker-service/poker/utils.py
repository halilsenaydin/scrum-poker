"""
Base Excel Export Class - Shared between Room and Sprint Admin
"""

import statistics
from collections import defaultdict, Counter

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule

class BaseExcelExport:

    COLORS = {
        'primary':    '366092',
        'header':     '4472C4',
        'success':    '63BE7B',
        'warning':    'FFEB84',
        'danger':     'F8696B',
        'info':       '5B9BD5',
        'accent':     'FFC000',
        'light_gray': 'E7E6E6',
    }

    # ── must be implemented by subclass ─────────────────────────────

    def get_sprints(self, queryset):
        raise NotImplementedError

    def get_export_title(self, queryset):
        raise NotImplementedError

    # ── public export entry points ───────────────────────────────────

    def export_basic(self, wb, queryset):
        """Level 1: Executive Summary, Sprint Overview, Tasks, Votes, Participants."""
        sprints = self.get_sprints(queryset)

        self._sheet_executive_summary(wb, sprints, queryset)
        self._sheet_sprint_overview(wb, sprints)
        self._sheet_tasks_by_sprint(wb, sprints)
        self._sheet_votes_by_sprint(wb, sprints)
        self._sheet_participants_by_sprint(wb, sprints)

        return wb

    def export_advanced(self, wb, queryset):
        """Level 2: Level 1 + analytics sheets with conditional formatting."""
        wb = self.export_basic(wb, queryset)
        sprints = self.get_sprints(queryset)

        self._sheet_consensus_analysis(wb, sprints)
        self._sheet_sprint_progress_analysis(wb, sprints)
        self._sheet_task_complexity(wb, sprints)
        self._sheet_risk_assessment(wb, sprints)
        self._sheet_estimation_accuracy(wb, sprints)
        self._sheet_team_dynamics(wb, sprints)

        return wb

    def export_full(self, wb, queryset):
        """Level 3: Level 2 + embedded charts, heatmap matrix, ML dataset."""
        wb = self.export_advanced(wb, queryset)
        sprints = self.get_sprints(queryset)

        self._sheet_consensus_chart(wb, sprints)
        self._sheet_sprint_progress_chart(wb, sprints)
        self._sheet_vote_distribution_chart(wb, sprints)
        self._sheet_task_participant_matrix(wb, sprints)
        self._sheet_participant_agreement_matrix(wb, sprints)
        self._sheet_outlier_detection(wb, sprints)

        return wb

    # backward-compat alias
    def export_to_excel(self, queryset):
        return self.export_full(queryset)

    # ════════════════════════════════════════════════════════════════
    # STATIC / PURE HELPERS
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _numeric_votes(task):
        """Return float values for all numeric votes on a task."""
        result = []
        for v in task.votes.all():
            try:
                result.append(float(v.vote))
            except (ValueError, TypeError):
                pass
        return result

    @staticmethod
    def _sp_total(tasks):
        """Sum story-points for an iterable of tasks (None-safe)."""
        return sum(t.sp for t in tasks if t.sp) or 0

    @staticmethod
    def _vote_stats(votes):
        """
        Return (avg, median, std, consensus_score) for a list of floats.
        Returns (None, None, None, None) when votes is empty.
        """
        if not votes:
            return None, None, None, None
        avg    = statistics.mean(votes)
        median = statistics.median(votes)
        std    = statistics.stdev(votes) if len(votes) > 1 else 0.0
        cons   = round(max(0.0, 100.0 - std * 10), 2)
        return round(avg, 2), round(median, 2), round(std, 2), cons

    @staticmethod
    def _complexity_label(avg, cv):
        if avg <= 3 and cv < 30:
            return "SIMPLE"
        if avg <= 5 and cv < 50:
            return "MODERATE"
        if avg <= 8:
            return "COMPLEX"
        return "VERY_COMPLEX"

    @staticmethod
    def _risk_label(consensus):
        if consensus >= 80:
            return "LOW"
        if consensus >= 50:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def _is_numeric(value):
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _vote_heatmap_color(vote_value):
        """Map a vote value to a hex background colour for the matrix."""
        try:
            v = float(vote_value)
        except (ValueError, TypeError):
            return 'E7E6E6'
        if v <= 1:  return 'C6EFCE'
        if v <= 3:  return '9FE1A3'
        if v <= 5:  return 'FFEB9C'
        if v <= 8:  return 'FFC7CE'
        if v <= 13: return 'FF9999'
        return 'FF6B6B'

    def _risk_color(self, label):
        return {
            'LOW':    self.COLORS['success'],
            'MEDIUM': self.COLORS['warning'],
            'HIGH':   self.COLORS['danger'],
        }[label]

    def _add_heatmap_legend(self, ws):
        """Add color legend for heatmap"""
        legend_row = ws.max_row + 3
        ws[f'A{legend_row}'] = "LEGEND:"
        ws[f'A{legend_row}'].font = Font(bold=True, size=11)
        
        legend_items = [
            ("0-1", self._vote_heatmap_color(1)),
            ("2-3", self._vote_heatmap_color(3)),
            ("4-5", self._vote_heatmap_color(5)),
            ("6-8", self._vote_heatmap_color(8)),
            ("9-13", self._vote_heatmap_color(13)),
            ("13+", self._vote_heatmap_color(14)),
        ]
        
        col = 2
        for range_text, color in legend_items:
            cell = ws.cell(row=legend_row, column=col)
            cell.value = range_text
            cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            cell.font = Font(bold=True, size=9)
            cell.alignment = Alignment(horizontal='center')
            cell.border = self._thin_border()
            col += 1

    # ════════════════════════════════════════════════════════════════
    # STYLE HELPERS
    # ════════════════════════════════════════════════════════════════

    def _thin_border(self):
        t = Side(style='thin', color='CCCCCC')
        return Border(left=t, right=t, top=t, bottom=t)

    def _color_cell(self, cell, hex_color, text_color='FFFFFF', bold=True):
        cell.fill      = PatternFill(start_color=hex_color,
                                     end_color=hex_color, fill_type='solid')
        cell.font      = Font(bold=bold, color=text_color)
        cell.alignment = Alignment(horizontal='center')

    def _apply_threshold_color(self, cell, value, low=50, high=80):
        color = (self.COLORS['success'] if value >= high
                 else self.COLORS['warning'] if value >= low
                 else self.COLORS['danger'])
        self._color_cell(cell, color)

    def _style_header(self, ws, row=1):
        for cell in ws[row]:
            cell.font      = Font(bold=True, color='FFFFFF', size=11)
            cell.fill      = PatternFill(start_color=self.COLORS['primary'],
                                         end_color=self.COLORS['primary'],
                                         fill_type='solid')
            cell.alignment = Alignment(horizontal='center',
                                       vertical='center', wrap_text=True)
            cell.border    = self._thin_border()
        ws.row_dimensions[row].height = 25

    def _section_header(self, ws, row, text):
        ws[f'A{row}'] = text
        ws[f'A{row}'].font      = Font(bold=True, size=12, color='FFFFFF')
        ws[f'A{row}'].fill      = PatternFill(start_color=self.COLORS['header'],
                                               end_color=self.COLORS['header'],
                                               fill_type='solid')
        ws[f'A{row}'].alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[row].height = 20
        ws.merge_cells(f'A{row}:B{row}')

    def _sheet_title_row(self, ws, text, n_cols=10):
        ws.merge_cells(f'A1:{get_column_letter(n_cols)}1')
        ws['A1'] = text
        ws['A1'].font      = Font(bold=True, size=14, color='FFFFFF')
        ws['A1'].fill      = PatternFill(start_color=self.COLORS['primary'],
                                         end_color=self.COLORS['primary'],
                                         fill_type='solid')
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 26

    def _auto_col_width(self, ws):
        for column in ws.columns:
            letter  = get_column_letter(column[0].column)
            max_len = max((len(str(c.value)) for c in column if c.value), default=0)
            ws.column_dimensions[letter].width = max(min(max_len + 3, 60), 10)

    def _freeze(self, ws, cell='A2'):
        ws.freeze_panes = cell

    def _cf_color_scale(self, ws, rng):
        ws.conditional_formatting.add(rng, ColorScaleRule(
            start_type='num', start_value=0,   start_color=self.COLORS['danger'],
            mid_type='num',   mid_value=50,    mid_color=self.COLORS['warning'],
            end_type='num',   end_value=100,   end_color=self.COLORS['success'],
        ))

    def _cf_databar(self, ws, rng, color=None):
        ws.conditional_formatting.add(rng, DataBarRule(
            start_type='min', end_type='max',
            color=color or self.COLORS['info'],
        ))

    # ── chart factory helpers ────────────────────────────────────────

    def _make_bar_chart(self, title, y_title='', x_title='',
                        height=14, width=22, grouping='clustered'):
        c = BarChart()
        c.title        = title
        c.y_axis.title = y_title
        c.x_axis.title = x_title
        c.height       = height
        c.width        = width
        c.grouping     = grouping
        c.overlap      = 100 if grouping == 'stacked' else 0
        return c

    def _make_pie_chart(self, title, height=14, width=18):
        c = PieChart()
        c.title  = title
        c.height = height
        c.width  = width
        return c

    def _pie_slice_colors(self, pie, hex_colors):
        """Apply per-slice fill colours to a PieChart's first series."""
        for idx, color in enumerate(hex_colors):
            pt = DataPoint(idx=idx)
            pt.graphicalProperties.solidFill = color
            pie.series[0].dPt.append(pt)

    # ════════════════════════════════════════════════════════════════
    # LEVEL 1 – BASIC SHEETS
    # ════════════════════════════════════════════════════════════════

    def _sheet_executive_summary(self, wb, sprints, queryset):
        ws       = wb.active
        ws.title = 'Executive Summary'
        self._sheet_title_row(ws, self.get_export_title(queryset), n_cols=8)
        row = 3

        self._section_header(ws, row, 'OVERALL STATISTICS'); row += 1

        total_sprints   = sprints.count()
        active_sprints  = sprints.filter(is_active=True).count()
        total_tasks     = sum(s.tasks.count() for s in sprints)
        completed_tasks = sum(s.tasks.filter(status='completed').count() for s in sprints)
        total_sp        = sum(self._sp_total(s.tasks.all()) for s in sprints)
        total_votes     = sum(t.get_vote_count()
                              for s in sprints for t in s.tasks.all())
        pid_set         = {v.participant_id
                           for s in sprints
                           for t in s.tasks.all()
                           for v in t.votes.all()}

        for label, value in [
            ('Total Sprints',      total_sprints),
            ('Active Sprints',     active_sprints),
            ('Total Participants', len(pid_set)),
            ('Total Tasks',        total_tasks),
            ('Completed Tasks',    completed_tasks),
            ('Total Votes',        total_votes),
            ('Total Story Points', total_sp),
        ]:
            ws[f'A{row}'] = f'{label}:'
            ws[f'A{row}'].font = Font(bold=True, size=11)
            ws[f'B{row}'] = value
            ws[f'B{row}'].font      = Font(size=11, color=self.COLORS['primary'], bold=True)
            ws[f'B{row}'].alignment = Alignment(horizontal='right')
            row += 1

        row += 1
        self._section_header(ws, row, 'SPRINT PROGRESS'); row += 1
        if total_tasks:
            cr = round(completed_tasks / total_tasks * 100, 1)
            ws[f'A{row}'] = 'Overall Completion Rate:'
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = f'{cr}%'
            self._apply_threshold_color(ws[f'B{row}'], cr)
            row += 1
            ws[f'A{row}'] = 'Avg SP per Task:'
            ws[f'B{row}'] = round(total_sp / total_tasks, 2)
            ws[f'B{row}'].font = Font(bold=True, color=self.COLORS['info'])
            row += 1

        row += 1
        self._section_header(ws, row, 'CONSENSUS ANALYSIS'); row += 1
        all_scores = []
        risk_dist  = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for s in sprints:
            for t in s.tasks.all():
                sc = t.metrics.get('consensus_score') if t.metrics else None
                if sc is not None:
                    all_scores.append(sc)
                    risk_dist[self._risk_label(sc)] += 1

        if all_scores:
            avg_c = round(statistics.mean(all_scores), 2)
            ws[f'A{row}'] = 'Average Consensus Score:'
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = f'{avg_c}%'
            self._apply_threshold_color(ws[f'B{row}'], avg_c)
            row += 1
            for label, key, color in [
                ('High Consensus (>80%)',     'LOW',    self.COLORS['success']),
                ('Medium Consensus (50-80%)', 'MEDIUM', self.COLORS['warning']),
                ('Low Consensus (<50%)',      'HIGH',   self.COLORS['danger']),
            ]:
                ws[f'A{row}'] = label
                ws[f'B{row}'] = risk_dist[key]
                self._color_cell(ws[f'B{row}'], color)
                row += 1

        row += 1
        self._section_header(ws, row, 'TOP INSIGHTS'); row += 1
        sprint_votes = {s: sum(t.get_vote_count() for t in s.tasks.all()) for s in sprints}
        sprint_cons, sprint_comp = {}, {}
        for s in sprints:
            scs = [t.metrics['consensus_score'] for t in s.tasks.all()
                   if t.metrics and 'consensus_score' in t.metrics]
            if scs:
                sprint_cons[s] = statistics.mean(scs)
            tc = s.tasks.count()
            cc = s.tasks.filter(status='completed').count()
            if tc:
                sprint_comp[s] = cc / tc * 100

        for label, mapping, suffix, color in [
            ('Most Active Sprint',       sprint_votes, 'votes', self.COLORS['primary']),
            ('Highest Consensus Sprint', sprint_cons,  '%',     self.COLORS['success']),
            ('Best Completion Sprint',   sprint_comp,  '%',     self.COLORS['success']),
        ]:
            if mapping:
                best = max(mapping, key=mapping.get)
                ws[f'A{row}'] = f'{label}:'
                ws[f'B{row}'] = f'{best.name}  ({round(mapping[best], 1)} {suffix})'
                ws[f'B{row}'].font = Font(color=color, bold=True)
                row += 1

        self._auto_col_width(ws)
        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 32

    # ────────────────────────────────────────────────────────────────

    def _sheet_sprint_overview(self, wb, sprints):
        ws = wb.create_sheet('Sprint Overview')
        ws.append([
            'Sprint Name', 'Room', 'Status', 'Is Active', 'Revealed',
            'Created At', 'Total Tasks', 'Completed', 'In Progress', 'Pending',
            'Total SP', 'Completed SP', 'Completion %',
            'Avg Consensus %', 'Total Votes', 'Unique Participants',
        ])
        self._style_header(ws)

        for s in sprints:
            tasks    = s.tasks.all()
            done     = tasks.filter(status='completed')
            tc       = tasks.count()
            total_sp = self._sp_total(tasks)
            done_sp  = self._sp_total(done)
            scores   = [t.metrics['consensus_score'] for t in tasks
                        if t.metrics and 'consensus_score' in t.metrics]
            pids     = {v.participant_id for t in tasks for v in t.votes.all()}
            ws.append([
                s.name, f'{s.room.name} - {s.room.room_code}',
                'Active' if s.is_active else 'Completed',
                '✓'    if s.is_active  else '✗',
                '✓'    if s.revealed  else '✗',
                s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
                tc, done.count(),
                tasks.filter(status='voting').count(),
                tasks.filter(status='pending').count(),
                total_sp, done_sp,
                round(done.count() / tc * 100, 1) if tc else 0,
                round(statistics.mean(scores), 1) if scores else 0,
                sum(t.get_vote_count() for t in tasks),
                len(pids),
            ])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'K2:K{last}')
            self._cf_color_scale(ws, f'L2:L{last}')
            self._cf_databar(ws,     f'M2:M{last}')

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_participants_by_sprint(self, wb, sprints):
        ws = wb.create_sheet('Participants by Sprint')
        ws.append([
            'Sprint Name', 'Room', 'Participant', 'Is Active',
            'Total Votes', 'Avg Vote', 'Most Common Vote', 'Tasks Participated', 'Activity %'
        ])
        self._style_header(ws)

        for s in sprints:
            pdata = defaultdict(lambda: {'votes': [], 'tasks': set()})
    
            for task in s.tasks.all():
                for v in task.votes.select_related('participant__user'):
                    pdata[v.participant]['votes'].append(v.vote)
                    pdata[v.participant]['tasks'].add(task.id)
            
            tc = s.tasks.count()

            for participant, d in pdata.items():
                nums = [float(v) for v in d['votes'] if self._is_numeric(v)]
                ws.append([
                    s.name, f'{s.room.name} - {s.room.room_code}', str(participant.user),
                    '✓'    if s.is_active  else '✗',
                    len(d['votes']),
                    round(statistics.mean(nums), 2) if nums else '-',
                    Counter(d['votes']).most_common(1)[0][0] if d['votes'] else '-',
                    len(d['tasks']),
                    round(len(d['tasks']) / tc * 100, 1) if tc else 0,
                ])

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_tasks_by_sprint(self, wb, sprints):
        ws = wb.create_sheet('Tasks by Sprint')
        ws.append([
            'Sprint Name', 'Room', 'Task ID', 'Title',
            'Status', 'SP', 'Vote Count', 'Avg Vote', 'Consensus %', 'Created At',
        ])
        self._style_header(ws)

        for s in sprints:
            for task in s.tasks.all():
                votes = self._numeric_votes(task)
                avg, _, _, cons = self._vote_stats(votes)
                ws.append([
                    s.name, f'{s.room.name} - {s.room.room_code}', task.id, task.title, task.status,
                    task.sp if task.sp is not None else '-',
                    task.get_vote_count(),
                    avg  if avg  is not None else '-',
                    cons if cons is not None else '-',
                    task.created_at.strftime('%Y-%m-%d %H:%M') if task.created_at else '',
                ])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'I2:I{last}')

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_votes_by_sprint(self, wb, sprints):
        ws = wb.create_sheet('Votes by Sprint')
        ws.append([
            'Sprint Name', 'Room', 'Task ID', 'Task Title',
            'Participant', 'Vote', 'Is Numeric', 'Voted At',
        ])
        self._style_header(ws)

        for s in sprints:
            for task in s.tasks.all():
                for v in task.votes.select_related('participant__user'):
                    ws.append([
                        s.name, f'{s.room.name} - {s.room.room_code}', task.id, task.title,
                        str(v.participant.user), v.vote,
                        '✓' if v.is_numeric() else '✗',
                        v.voted_at.strftime('%Y-%m-%d %H:%M:%S') if v.voted_at else '',
                    ])

        self._auto_col_width(ws)
        self._freeze(ws)

    # ════════════════════════════════════════════════════════════════
    # LEVEL 2 – ANALYTICS SHEETS
    # ════════════════════════════════════════════════════════════════

    def _sheet_consensus_analysis(self, wb, sprints):
        ws = wb.create_sheet('Consensus Analysis')
        ws.append([
            'Sprint Name', 'Room', 'Task ID', 'Task Title',
            'Vote Count', 'Avg', 'Median', 'Min', 'Max', 'Std Dev', 'Consensus %',
        ])
        self._style_header(ws)

        for s in sprints:
            for task in s.tasks.all():
                votes = self._numeric_votes(task)
                if not votes:
                    continue
                avg, median, std, cons = self._vote_stats(votes)
                ws.append([
                    s.name, f'{s.room.name} - {s.room.room_code}', task.id, task.title,
                    len(votes), avg, median, min(votes), max(votes), std, cons,
                ])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'K2:K{last}')

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_sprint_progress_analysis(self, wb, sprints):
        ws = wb.create_sheet('Sprint Progress')
        ws.append([
            'Sprint Name', 'Room',
            'Total Tasks', 'Completed', 'In Progress', 'Pending',
            'Total SP', 'Completed SP', 'Remaining SP', 'Completion %', 'Velocity (SP)',
        ])
        self._style_header(ws)

        for s in sprints:
            tasks    = s.tasks.all()
            done     = tasks.filter(status='completed')
            tc       = tasks.count()
            total_sp = self._sp_total(tasks)
            done_sp  = self._sp_total(done)
            ws.append([
                s.name, f'{s.room.name} - {s.room.room_code}', tc,
                done.count(),
                tasks.filter(status='voting').count(),
                tasks.filter(status='pending').count(),
                total_sp, done_sp, total_sp - done_sp,
                round(done.count() / tc * 100, 1) if tc else 0,
                done_sp,
            ])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'J2:J{last}')
            self._cf_databar(ws, f'G2:G{last}', color=self.COLORS['primary'])

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_task_complexity(self, wb, sprints):
        ws = wb.create_sheet('Task Complexity')
        ws.append([
            'Sprint', 'Room', 'Task ID', 'Title',
            'Votes', 'Avg', 'Std Dev', 'CV', 'Consensus %', 'Complexity',
        ])
        self._style_header(ws)

        complexity_color = {
            'SIMPLE':       self.COLORS['success'],
            'MODERATE':     self.COLORS['info'],
            'COMPLEX':      self.COLORS['warning'],
            'VERY_COMPLEX': self.COLORS['danger'],
        }

        for s in sprints:
            for task in s.tasks.all():
                votes = self._numeric_votes(task)
                if not votes:
                    continue
                avg, _, std, cons = self._vote_stats(votes)
                cv         = round(std / avg * 100, 2) if avg else 0
                complexity = self._complexity_label(avg, cv)
                ws.append([
                    s.name, f'{s.room.name} - {s.room.room_code}', task.id, task.title,
                    len(votes), avg, std, cv, cons, complexity,
                ])
                self._color_cell(ws.cell(ws.max_row, 10), complexity_color[complexity])

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_risk_assessment(self, wb, sprints):
        ws = wb.create_sheet('Risk Assessment')
        ws.append([
            'Sprint', 'Room', 'Task', 'Risk Level',
            'Risk Score', 'Consensus %', 'Vote Spread', 'Outlier Count', 'Recommendation',
        ])
        self._style_header(ws)

        recs = {
            'HIGH':   'Re-discuss – significant disagreement',
            'MEDIUM': 'Review outliers – brief clarification needed',
            'LOW':    'Proceed with estimation',
        }

        for s in sprints:
            for task in s.tasks.all():
                votes = self._numeric_votes(task)
                if not votes:
                    continue
                avg, _, std, cons = self._vote_stats(votes)
                spread   = max(votes) - min(votes)
                outliers = sum(1 for v in votes if abs(v - avg) > 2 * std) if std else 0
                score    = round((100 - cons) * 0.4
                                 + min(spread * 5, 40)
                                 + min(outliers * 10, 20), 2)
                risk = self._risk_label(cons)
                ws.append([
                    s.name, f'{s.room.name} - {s.room.room_code}', task.title,
                    risk, score, cons, round(spread, 2), outliers, recs[risk],
                ])
                self._color_cell(ws.cell(ws.max_row, 4), self._risk_color(risk))

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_estimation_accuracy(self, wb, sprints):
        ws = wb.create_sheet('Estimation Accuracy')
        ws.append(['Sprint', 'Room', 'Task', 'Avg Vote', 'Final SP', 'Diff', 'Accuracy %'])
        self._style_header(ws)

        for s in sprints:
            for task in s.tasks.all():
                if not task.sp:
                    continue
                votes = self._numeric_votes(task)
                if not votes:
                    continue
                avg  = statistics.mean(votes)
                diff = abs(task.sp - avg)
                acc  = round(100 - min(diff / task.sp * 100, 100), 2)
                ws.append([s.name, f'{s.room.name} - {s.room.room_code}', task.title,
                            round(avg, 2), task.sp, round(diff, 2), acc])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'G2:G{last}')

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_team_dynamics(self, wb, sprints):
        ws = wb.create_sheet('Team Dynamics')
        ws.append([
            'Sprint', 'Room', 'Room Participants', 'Sprint Active Participants',
            'Participation %', 'Team Cohesion %',
        ])
        self._style_header(ws)

        for s in sprints:
            pids       = {v.participant_id for t in s.tasks.all() for v in t.votes.all()}
            room_total = s.room.participants.count()
            scores     = [t.metrics['consensus_score'] for t in s.tasks.all()
                          if t.metrics and 'consensus_score' in t.metrics]
            ws.append([
                s.name, f'{s.room.name} - {s.room.room_code}', room_total, len(pids),
                round(len(pids) / room_total * 100, 1) if room_total else 0,
                round(statistics.mean(scores), 2) if scores else 0,
            ])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'F2:F{last}')

        self._auto_col_width(ws)
        self._freeze(ws)

    # ════════════════════════════════════════════════════════════════
    # LEVEL 3 – SHEETS WITH EMBEDDED CHARTS
    # ════════════════════════════════════════════════════════════════

    def _sheet_consensus_chart(self, wb, sprints):
        """
        One sheet per sprint.
          Cols A-H : data table (task consensus stats).
          Cols J+  : BarChart (consensus % per task)
                     PieChart (High / Medium / Low task distribution).
        Helper data for the pie is stored in cols N-O (narrow, inconspicuous).
        """
        for sprint in sprints:
            safe = sprint.name[:25].strip().replace('/', '-').replace('\\', '-')
            ws   = wb.create_sheet(f'C-{safe}')

            self._sheet_title_row(
                ws,
                f'Consensus Chart – {sprint.name} ({sprint.room.name})',
                n_cols=8,
            )

            ws.append(['Task Title', 'Votes', 'Avg', 'Median',
                       'Min', 'Max', 'Std Dev', 'Consensus %'])
            self._style_header(ws, row=2)
            data_start = 3

            for task in sprint.tasks.all():
                votes = self._numeric_votes(task)
                if not votes:
                    continue
                avg, median, std, cons = self._vote_stats(votes)
                ws.append([task.title, len(votes), avg, median,
                            min(votes), max(votes), std, cons])

            data_end = ws.max_row
            if data_end < data_start:
                continue

            self._cf_color_scale(ws, f'H{data_start}:H{data_end}')
            self._auto_col_width(ws)
            ws.column_dimensions['A'].width = 42

            # ── BarChart: consensus % per task ───────────────────────
            bar = self._make_bar_chart(
                title=f'Consensus Score – {sprint.name}',
                y_title='Consensus %', x_title='Tasks',
            )
            bar.add_data(
                Reference(ws, min_col=8, max_col=8, min_row=2, max_row=data_end),
                titles_from_data=True,
            )
            bar.set_categories(
                Reference(ws, min_col=1, min_row=data_start, max_row=data_end)
            )
            bar.series[0].graphicalProperties.solidFill = self.COLORS['info']
            ws.add_chart(bar, 'J3')

            # ── Count risk levels from the data column ───────────────
            high = medium = low = 0
            for r in range(data_start, data_end + 1):
                val = ws.cell(row=r, column=8).value
                if val is None:
                    continue
                if   val >= 80: low    += 1
                elif val >= 50: medium += 1
                else:           high   += 1

            # helper table cols N-O (14-15)
            htop = data_end + 3
            ws.cell(htop,     14, 'Level');         ws.cell(htop,     15, 'Count')
            ws.cell(htop + 1, 14, 'High (>80%)');   ws.cell(htop + 1, 15, low)
            ws.cell(htop + 2, 14, 'Med (50-80%)');  ws.cell(htop + 2, 15, medium)
            ws.cell(htop + 3, 14, 'Low (<50%)');    ws.cell(htop + 3, 15, high)
            ws.column_dimensions['N'].width = 14
            ws.column_dimensions['O'].width = 10

            # ── PieChart: risk distribution ──────────────────────────
            pie = self._make_pie_chart('Risk Distribution', height=12, width=16)
            pie.add_data(
                Reference(ws, min_col=15, min_row=htop, max_row=htop + 3),
                titles_from_data=True,
            )
            pie.set_categories(
                Reference(ws, min_col=14, min_row=htop + 1, max_row=htop + 3)
            )
            self._pie_slice_colors(pie, [
                self.COLORS['success'],   # High consensus → Low risk
                self.COLORS['warning'],   # Medium
                self.COLORS['danger'],    # Low consensus  → High risk
            ])
            ws.add_chart(pie, 'J22')
            self._freeze(ws, 'A3')

    # ────────────────────────────────────────────────────────────────

    def _sheet_sprint_progress_chart(self, wb, sprints):
        """
        Single sheet.
          Cols A-H : sprint progress data table.
          Cols J+  : Stacked BarChart (Completed / In-Progress / Pending per sprint).
                     BarChart (Total SP per sprint).
        """
        ws = wb.create_sheet('Sprint Progress Chart')
        self._sheet_title_row(ws, 'Sprint Progress Overview', n_cols=8)

        ws.append(['Sprint Name', 'Room', 'Total Tasks',
                   'Completed', 'In Progress', 'Pending',
                   'Total SP', 'Completion %'])
        self._style_header(ws, row=2)
        data_start = 3

        for s in sprints:
            tasks    = s.tasks.all()
            done     = tasks.filter(status='completed')
            tc       = tasks.count()
            total_sp = self._sp_total(tasks)
            ws.append([
                s.name, f'{s.room.name} - {s.room.room_code}', tc,
                done.count(),
                tasks.filter(status='voting').count(),
                tasks.filter(status='pending').count(),
                total_sp,
                round(done.count() / tc * 100, 1) if tc else 0,
            ])

        data_end = ws.max_row
        if data_end >= data_start:
            self._cf_color_scale(ws, f'H{data_start}:H{data_end}')
            self._cf_databar(ws, f'G{data_start}:G{data_end}',
                             color=self.COLORS['primary'])

        self._auto_col_width(ws)

        if data_end < data_start:
            return

        cats = Reference(ws, min_col=1, min_row=data_start, max_row=data_end)

        # ── Stacked BarChart: task status per sprint ─────────────────
        bar = self._make_bar_chart(
            title='Task Status by Sprint',
            y_title='Tasks', x_title='Sprints',
            height=16, width=28, grouping='stacked',
        )
        for col, color in [
            (4, self.COLORS['success']),   # Completed
            (5, self.COLORS['warning']),   # In Progress
            (6, self.COLORS['danger']),    # Pending
        ]:
            bar.add_data(
                Reference(ws, min_col=col, max_col=col, min_row=2, max_row=data_end),
                titles_from_data=True,
            )
            bar.series[-1].graphicalProperties.solidFill = color
        bar.set_categories(cats)
        ws.add_chart(bar, 'J3')

        # ── BarChart: SP per sprint ──────────────────────────────────
        sp_bar = self._make_bar_chart(
            title='Story Points per Sprint',
            y_title='SP', x_title='Sprints',
            height=12, width=22,
        )
        sp_bar.add_data(
            Reference(ws, min_col=7, max_col=7, min_row=2, max_row=data_end),
            titles_from_data=True,
        )
        sp_bar.set_categories(
            Reference(ws, min_col=1, min_row=data_start, max_row=data_end)
        )
        sp_bar.series[0].graphicalProperties.solidFill = self.COLORS['primary']
        ws.add_chart(sp_bar, 'J28')

        self._freeze(ws, 'A3')

    # ────────────────────────────────────────────────────────────────

    def _sheet_vote_distribution_chart(self, wb, sprints):
        """
        Left  (A:F)  : detail table – vote distribution per task per sprint.
        Right (H+)   : PieChart (global vote share per value).
                       BarChart (frequency per vote value).
        Helper data written to cols N-O.
        """
        ws = wb.create_sheet('Vote Distribution Chart')
        self._sheet_title_row(ws, 'Vote Distribution Analysis', n_cols=6)

        ws.append(['Sprint', 'Room', 'Task', 'Vote Value', 'Count', 'Percentage'])
        self._style_header(ws, row=2)

        global_dist: dict = {}
        for s in sprints:
            for task in s.tasks.all():
                dist = (task.metrics or {}).get('distribution', {})
                if not dist:
                    continue
                total = sum(dist.values())
                for val, cnt in sorted(dist.items(), key=lambda x: str(x[0])):
                    ws.append([s.name, f'{s.room.name} - {s.room.room_code}', task.title,
                                val, cnt,
                                round(cnt / total * 100, 2) if total else 0])
                    global_dist[str(val)] = global_dist.get(str(val), 0) + cnt

        self._auto_col_width(ws)

        if not global_dist:
            return

        # helper table cols N-O (14-15)
        htop = 2
        ws.cell(htop, 14, 'Vote Value')
        ws.cell(htop, 15, 'Total Count')
        sorted_vals = sorted(global_dist.items(), key=lambda x: str(x[0]))
        for i, (val, cnt) in enumerate(sorted_vals, start=1):
            ws.cell(htop + i, 14, val)
            ws.cell(htop + i, 15, cnt)
        h_start = htop + 1
        h_end   = htop + len(sorted_vals)
        ws.column_dimensions['N'].width = 14
        ws.column_dimensions['O'].width = 12

        # ── PieChart ─────────────────────────────────────────────────
        pie = self._make_pie_chart('Vote Distribution', height=14, width=20)
        pie.add_data(
            Reference(ws, min_col=15, min_row=htop, max_row=h_end),
            titles_from_data=True,
        )
        pie.set_categories(
            Reference(ws, min_col=14, min_row=h_start, max_row=h_end)
        )
        ws.add_chart(pie, 'H3')

        # ── BarChart: frequency per vote value ───────────────────────
        bar = self._make_bar_chart(
            title='Vote Frequency by Value',
            y_title='Count', x_title='Vote Value',
            height=12, width=20,
        )
        bar.add_data(
            Reference(ws, min_col=15, min_row=htop, max_row=h_end),
            titles_from_data=True,
        )
        bar.set_categories(
            Reference(ws, min_col=14, min_row=h_start, max_row=h_end)
        )
        bar.series[0].graphicalProperties.solidFill = self.COLORS['info']
        ws.add_chart(bar, 'H24')

        self._freeze(ws, 'A3')

    # ────────────────────────────────────────────────────────────────

    def _sheet_task_participant_matrix(self, wb, sprints):
        """
        Heat-map grid per sprint: rows = tasks, cols = participants.
        Cells colour-coded by vote magnitude.
        """
        ws = wb.create_sheet('Voting Matrix')

        for sprint in sprints:
            pids = {v.participant_id
                    for t in sprint.tasks.all()
                    for v in t.votes.all()}
            participants = list(
                sprint.room.participants.filter(id__in=pids)
                .order_by('user__username')
            )
            if not participants:
                continue

            if ws.max_row > 1:
                ws.append([])
                ws.append([])

            sprint_row = ws.max_row + 1
            n_cols     = len(participants) + 2
            ws.append([f'SPRINT: {sprint.name}  |  {sprint.room.name}'])
            ws.merge_cells(
                f'A{sprint_row}:{get_column_letter(n_cols)}{sprint_row}'
            )
            ws[f'A{sprint_row}'].font      = Font(bold=True, size=13, color='FFFFFF')
            ws[f'A{sprint_row}'].fill      = PatternFill(
                start_color=self.COLORS['primary'],
                end_color=self.COLORS['primary'], fill_type='solid')
            ws[f'A{sprint_row}'].alignment = Alignment(horizontal='center')
            ws.row_dimensions[sprint_row].height = 22

            ws.append(['Task', 'Avg'] + [str(p.user) for p in participants])
            hrow = ws.max_row
            for cell in ws[hrow]:
                cell.font      = Font(bold=True, color='FFFFFF')
                cell.fill      = PatternFill(start_color=self.COLORS['header'],
                                              end_color=self.COLORS['header'],
                                              fill_type='solid')
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
                cell.border    = self._thin_border()

            for task in sprint.tasks.all():
                nums     = self._numeric_votes(task)
                avg_val  = round(statistics.mean(nums), 1) if nums else '-'
                row_data = [task.title, avg_val]
                for p in participants:
                    vote_obj = task.get_participant_vote(p)
                    row_data.append(vote_obj.vote if vote_obj else '')
                ws.append(row_data)

                cur = ws.max_row
                for col_idx, cell in enumerate(ws[cur], start=1):
                    cell.border    = self._thin_border()
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    if col_idx > 2 and cell.value != '':
                        bg        = self._vote_heatmap_color(cell.value)
                        cell.fill = PatternFill(start_color=bg, end_color=bg,
                                                fill_type='solid')
                        cell.font = Font(bold=True)

        ws.column_dimensions['A'].width = 42
        ws.column_dimensions['B'].width = 8

        for col in range(3, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = 13

        # Add legend
        self._add_heatmap_legend(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_participant_agreement_matrix(self, wb, sprints):
        ws = wb.create_sheet('Agreement Matrix')
        ws.append([
            'Sprint', 'Room', 'Participant 1', 'Participant 2',
            'Common Tasks', 'Agreement %', 'Avg Vote Diff',
        ])
        self._style_header(ws)

        for s in sprints:
            pids  = {v.participant_id for t in s.tasks.all() for v in t.votes.all()}
            parts = list(s.room.participants.filter(id__in=pids))

            for i, p1 in enumerate(parts):
                for p2 in parts[i + 1:]:
                    p1_map = {v.task_id: v.vote for v in p1.votes.all()}
                    p2_map = {v.task_id: v.vote for v in p2.votes.all()}
                    common = set(p1_map) & set(p2_map)
                    if not common:
                        continue
                    agreements, diffs = 0, []
                    for tid in common:
                        if p1_map[tid] == p2_map[tid]:
                            agreements += 1
                        try:
                            diffs.append(abs(float(p1_map[tid]) - float(p2_map[tid])))
                        except (ValueError, TypeError):
                            pass
                    ws.append([
                        s.name, f'{s.room.name} - {s.room.room_code}', str(p1.user), str(p2.user),
                        len(common),
                        round(agreements / len(common) * 100, 2),
                        round(statistics.mean(diffs), 2) if diffs else 0,
                    ])

        last = ws.max_row
        if last > 1:
            self._cf_color_scale(ws, f'F2:F{last}')

        self._auto_col_width(ws)
        self._freeze(ws)

    # ────────────────────────────────────────────────────────────────

    def _sheet_outlier_detection(self, wb, sprints):
        ws = wb.create_sheet('Outliers')
        ws.append([
            'Sprint', 'Room', 'Task', 'Participant',
            'Vote', 'Task Avg', 'Deviation', 'Is Outlier',
        ])
        self._style_header(ws)

        for s in sprints:
            for task in s.tasks.all():
                votes = self._numeric_votes(task)
                if len(votes) < 3:
                    continue
                avg = statistics.mean(votes)
                std = statistics.stdev(votes)
                for v in task.votes.all():
                    try:
                        vf = float(v.vote)
                    except (ValueError, TypeError):
                        continue
                    deviation  = abs(vf - avg)
                    is_outlier = std > 0 and deviation > 2 * std
                    ws.append([
                        s.name, f'{s.room.name} - {s.room.room_code}', task.title, str(v.participant.user),
                        vf, round(avg, 2), round(deviation, 2),
                        'YES' if is_outlier else 'NO',
                    ])
                    if is_outlier:
                        for col in range(1, 9):
                            ws.cell(ws.max_row, col).fill = PatternFill(
                                start_color='FFC7CE', end_color='FFC7CE',
                                fill_type='solid')

        self._auto_col_width(ws)
        self._freeze(ws)
