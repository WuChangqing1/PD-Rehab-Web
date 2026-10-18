"""Permanent number reservations, independent of patient UUIDs and soft deletion."""
from sqlalchemy import BigInteger,Integer
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base


class PatientNumberAllocation(Base):
    __tablename__='patient_number_allocations'
    __table_args__={'sqlite_autoincrement':True}
    id:Mapped[int]=mapped_column(BigInteger().with_variant(Integer,'sqlite'),primary_key=True,autoincrement=True)
