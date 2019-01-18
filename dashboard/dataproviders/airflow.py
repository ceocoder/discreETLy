from functools import reduce
from dashboard.utils import clean_dag_id

from dashboard.models import DagRun, TaskInstance


class AirflowDBDataProvider:

    def __init__(self, config, logger, client):
        self.logger = logger
        self.config = config
        self.client = client

    def get_dag_state(self, dag_id, execution_date):
        SQL = f"""
        SELECT state FROM dag_run
        WHERE dag_id = '{dag_id}'
        AND execution_date = '{execution_date}'
        """
        result = self.client.query(SQL)
        return result[0]['state']

    def get_history(self, days):
        SQL = f'''
        SELECT
            a.dag_id,
            a.execution_date as date,
            a.state
        FROM dag_run a
        INNER JOIN (
            SELECT dag_id, MAX(execution_date) as date
            FROM dag_run
            WHERE execution_date >= DATE_ADD(CURDATE(), INTERVAL -{days} DAY)
            GROUP BY dag_id
        ) b ON
            a.dag_id = b.dag_id
            AND a.execution_date = b.date
        '''
        data = self.client.query(SQL)

        dag_names = set(map(lambda row: clean_dag_id(row['dag_id']), data))

        return {dag_name: reversed([DagRun(**row) for row in data if clean_dag_id(row['dag_id']) == dag_name])
                for dag_name in dag_names}

    def get_last_successful_tasks(self):
        last_successful_task_end_date = '''
        SELECT dag_id, task_id, max(end_date) as end_date
        FROM task_instance
        WHERE state = "success"
        GROUP BY dag_id, task_id
        '''

        data = self.client.query(last_successful_task_end_date)
        result = {}

        for row in data:
            row['dag_name'] = clean_dag_id(row['dag_id'])
            key = row['dag_name'] + row['task_id']
            if key in result and row['end_date'] and result[key].end_date > row['end_date']:
                continue # duplicate with dag old version
            result[key] = TaskInstance(**row)

        return list(result.values())

    def get_newest_task_instances(self):
        newest_task_instances_sql = '''
        SELECT dr.dag_id,
            dr.execution_date,
            ti.task_id,
            ti.state as dag_state,
            ti.duration,
            ti.start_date,
            ti.end_date
        FROM (
        SELECT dag_id,
            MAX(execution_date) as execution_date
        FROM dag_run
            GROUP BY dag_id) dr
        INNER JOIN task_instance ti
        ON dr.dag_id = ti.dag_id AND
        dr.execution_date = ti.execution_date'''.replace("\n", "")

        data = self.client.query(newest_task_instances_sql)
        result = {}

        for row in data:
            row['dag_name'] = clean_dag_id(row['dag_id'])
            key = row['dag_name'] + row['task_id']
            if key in result and row['end_date'] and result[key].end_date > row['end_date']:
                continue # duplicate with dag old version
            result[key] = TaskInstance(**row)

        return list(result.values())

    def get_dag_tasks(self, dag_id, execution_date):
        data = self.client.query(
            f"""SELECT dag_id, execution_date, task_id, start_date, end_date, duration, state as task_state
            FROM task_instance WHERE dag_id='{dag_id}' AND execution_date='{execution_date}'""".replace("\n", ""))
        return [TaskInstance(**row) for row in data]

    def get_report_table_state(self, report_tables):

        statuses = '","'.join(
            reduce(
                lambda x, y: x + y,
                list(report_tables.values())
                )
            )

        query = f'SELECT task_id, state from' \
                f'(SELECT task_id, state, max(execution_date) FROM task_instance ' \
                f'where task_id in  ("{statuses}") group by task_id, state) a'

        return self.client.query(query)


    def get_dags_status(self):
        '''
        For each non-technical DAG returns the name and the state of last run
        :return:
        '''

        latest_dags_status_sql = '''
        SELECT
           dr.dag_id,
           dr.state
        FROM dag_run dr
        INNER JOIN (SELECT
                        dag_id,
                        MAX(execution_date) AS date
                    FROM dag_run
                    GROUP BY dag_id) mx
            ON
            dr.dag_id = mx.dag_id
            AND dr.execution_date = mx.date
        '''.replace("\n", "")
        return [{
            'name': clean_dag_id(dag['dag_id']),
            'state': dag['state']}
            for dag in self.client.query(latest_dags_status_sql)
            if clean_dag_id(dag['dag_id']) not in self.config.get('TECHNICAL_ETLS', set())]
