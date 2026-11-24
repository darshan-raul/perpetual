"""Generated Python failover script for the P1c PoC compile loop (spec §63.2, P1c-04)."""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, StrictUndefined


def render_poc_recovery_script(
    *,
    stack_name: str,
    primary_region: str,
    target_region: str,
    rds_replica_id: str,
    ecs_cluster: str,
    ecs_service: str,
    ecs_target_desired_count: int = 4,
    dr_health_check_url: str = "https://dr.checkout.example.com/health",
) -> str:
    """Render a self-contained, resumable, dry-run Python failover script (P1c-04)."""
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    template_source = (
        files("perpetual.runbooks")
        .joinpath("templates", "failover.py.j2")
        .read_text(encoding="utf-8")
    )
    return env.from_string(template_source).render(
        stack_name=stack_name,
        primary_region=primary_region,
        target_region=target_region,
        rds_replica_id=rds_replica_id,
        ecs_cluster=ecs_cluster,
        ecs_service=ecs_service,
        ecs_target_desired_count=ecs_target_desired_count,
        dr_health_check_url=dr_health_check_url,
    )
