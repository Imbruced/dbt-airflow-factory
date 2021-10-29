import os

from airflow import DAG
from airflow.operators.dummy import DummyOperator
from pytimeparse import parse

from dbt_airflow_manifest_parser.builder_factory import DbtAirflowTasksBuilderFactory
from dbt_airflow_manifest_parser.config_utils import read_config


class AirflowDagFactory:
    def __init__(
        self,
        config_path,
        env: str,
        dbt_config_file_name: str = "dbt.yml",
        k8s_config_file_name: str = "k8s.yml",
        airflow_config_file_name: str = "airflow.yml",
    ):
        self._builder = DbtAirflowTasksBuilderFactory(
            config_path, env, dbt_config_file_name, k8s_config_file_name
        ).create()
        self.config_path = config_path
        self.env = env
        self.airflow_config_file_name = airflow_config_file_name

    def create(self) -> DAG:
        config = self._read_config()
        with DAG(default_args=config["default_args"], **config["dag"]) as dag:
            start = DummyOperator(task_id="start")
            if config.get("seek_task", True):
                start = self._builder.create_seed_task()
            tasks = self._builder.parse_manifest_into_tasks(
                self._manifest_file_path(config)
            )
            for starting_task in tasks.get_starting_tasks():
                start >> starting_task.run_airflow_task
            for ending_task in tasks.get_ending_tasks():
                ending_task.test_airflow_task >> DummyOperator(task_id="end")
            return dag

    def _manifest_file_path(self, config: dict) -> str:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(file_dir, config["manifest_file_name"])

    def _read_config(self) -> dict:
        config = read_config(self.config_path, self.env, self.airflow_config_file_name)
        if "retry_delay" in config["default_args"]:
            config["default_args"]["retry_delay"] = parse(
                config["default_args"]["retry_delay"]
            )
        return config
