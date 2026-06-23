"""People — students, guardians, employees, teachers."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class Student(BaseEntity, Base):
    __tablename__ = "student"

    admission_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    roll_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped["Date"] = mapped_column(Date, nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    permanent_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    government_id_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    government_id_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True, index=True)

    enrollment_status: Mapped[str] = mapped_column(String(32), default="enrolled", nullable=False)
    # enrolled / promoted / graduated / transferred / dropped
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Extended personal / admission details
    admission_date: Mapped["Date"] = mapped_column(Date, nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)  # General/OBC/SC/ST/EWS
    religion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mother_tongue: Mapped[str | None] = mapped_column(String(40), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(40), nullable=True)  # Aadhaar / national ID
    house: Mapped[str | None] = mapped_column(String(40), nullable=True)  # school house
    previous_school: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Guardian(BaseEntity, Base):
    __tablename__ = "guardian"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    relation: Mapped[str] = mapped_column(String(50), default="father", nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    government_id_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    government_id_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Employee(BaseEntity, Base):
    __tablename__ = "employee"

    employee_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    government_id_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    government_id_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    date_of_joining: Mapped["Date"] = mapped_column(Date, nullable=True)
    employment_type: Mapped[str] = mapped_column(String(32), default="full_time", nullable=False)
    salary: Mapped["Numeric"] = mapped_column(Numeric(12, 2), nullable=True)
    employment_status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Teacher(BaseEntity, Base):
    """A teaching role layered on an employee record."""

    __tablename__ = "teacher"

    employee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("employee.id"), index=True)
    qualification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    experience_years: Mapped[int | None] = mapped_column(nullable=True)


class TeacherProfile(BaseEntity, Base):
    """Teaching capability and compliance profile for one employee."""

    __tablename__ = "teacher_profile"

    employee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("employee.id"), index=True)
    expertise: Mapped[str | None] = mapped_column(Text, nullable=True)
    certifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    subjects_can_teach: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("employee.id"), nullable=True)


class TeacherAssignment(BaseEntity, Base):
    """Maps a teacher to a class/section/subject for a date range."""

    __tablename__ = "teacher_assignment"

    employee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("employee.id"), index=True)
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("subject.id"), nullable=True, index=True)
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("employee.id"), nullable=True)
    effective_from: Mapped["Date"] = mapped_column(Date, nullable=True)
    effective_to: Mapped["Date"] = mapped_column(Date, nullable=True)
    assignment_status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
