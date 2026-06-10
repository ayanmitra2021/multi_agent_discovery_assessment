from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    csp = Column(String, nullable=False, index=True)
    control_code = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)   # security | networking | operations | architecture | cost
    severity = Column(String, nullable=False)   # critical | high | medium | low
    is_mandatory = Column(Boolean, default=False, nullable=False)
    description = Column(Text)
    source_ref = Column(String)

    framework_mappings = relationship("FrameworkControl", back_populates="policy")


class ApprovedService(Base):
    __tablename__ = "approved_services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    csp = Column(String, nullable=False, index=True)
    service_name = Column(String, nullable=False)
    service_category = Column(String, nullable=False)  # compute | database | storage | networking | security | messaging | analytics | ai
    capability_tags = Column(JSON, default=list)        # e.g. ["containers", "serverless"]
    status = Column(String, default="approved")         # approved | conditional | deprecated
    constraints_note = Column(Text)


class ComplianceFramework(Base):
    __tablename__ = "compliance_frameworks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    framework_code = Column(String, unique=True, nullable=False)
    framework_name = Column(String, nullable=False)
    jurisdiction = Column(String)   # US | EU | International | UK | APAC
    version = Column(String)

    policy_mappings = relationship("FrameworkControl", back_populates="framework")


class FrameworkControl(Base):
    """Maps compliance framework requirements to internal policy controls."""
    __tablename__ = "framework_controls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    mapping_note = Column(Text)

    framework = relationship("ComplianceFramework", back_populates="policy_mappings")
    policy = relationship("Policy", back_populates="framework_mappings")


class PastMigration(Base):
    __tablename__ = "past_migrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    csp = Column(String, nullable=False, index=True)
    source_pattern = Column(String, nullable=False)     # e.g. "VB6 + SQL Server 2008"
    target_pattern = Column(String, nullable=False)     # e.g. ".NET 8 on ECS Fargate + RDS"
    app_archetype = Column(String, nullable=False)      # web | api | batch | desktop | analytics | database | mobile
    complexity_tier = Column(String, nullable=False)    # low | medium | high | critical
    outcome = Column(String, default="success")         # success | partial | cancelled
    duration_weeks = Column(Integer)
    lessons_learned = Column(Text)


def create_db_engine(db_url: str):
    """
    Create a SQLAlchemy engine.  SQLite gets check_same_thread=False
    (needed for FastAPI async context) and StaticPool for in-memory DBs
    (keeps the same connection so tests share schema + data).
    """
    connect_args = {}
    pool_kwargs = {}

    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in db_url:
            pool_kwargs["poolclass"] = StaticPool

    return create_engine(db_url, connect_args=connect_args, echo=False, **pool_kwargs)


def init_db(engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
