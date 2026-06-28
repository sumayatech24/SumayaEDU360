"""Import every model so SQLAlchemy's metadata is fully populated."""
from app.models.academic import (  # noqa: F401
    AcademicYear,
    Grade,
    Program,
    Section,
    Semester,
    Subject,
    Topic,
)
from app.models.admissions import (  # noqa: F401
    AdmissionApplicant,
    AdmissionApplication,
    AdmissionCharge,
    AdmissionDocument,
    AdmissionLead,
    AdmissionVerification,
)
from app.models.attendance import Attendance  # noqa: F401
from app.models.auth import (  # noqa: F401
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.exams import Exam, ExamSubject, Marks, MarksBatch, QuestionPaper  # noqa: F401
from app.models.fees import (  # noqa: F401
    FeePlan,
    FeePlanComponent,
    Invoice,
    Payment,
)
from app.models.meta import (  # noqa: F401
    AuditLog,
    Document,
    EntityDef,
    EntityRecord,
    FieldDef,
    MasterType,
    MasterValue,
    MenuItem,
    Module,
    ModuleCapability,
    Notification,
    Setting,
)
from app.models.academics_ops import (  # noqa: F401
    CurriculumPlan,
    Homework,
    HomeworkSubmission,
    LessonPlan,
    TimetablePeriod,
)
from app.models.finance import (  # noqa: F401
    Expense,
    LedgerAccount,
    PurchaseOrder,
    Vendor,
)
from app.models.content import (  # noqa: F401
    KnowledgeArticle,
    LearningResource,
    PtmMeeting,
    QuestionBankItem,
)
from app.models.hostel import (  # noqa: F401
    HostelAllocation,
    HostelAttendance,
    HostelBed,
    HostelBlock,
    HostelIncident,
    HostelRoom,
    HostelVisitor,
)
from app.models.operations import (  # noqa: F401
    Activity,
    ActivityRegistration,
    Announcement,
    AssetAssignment,
    Banner,
    CmsPage,
    InventoryItem,
    MealMenu,
    MealPlan,
    StockMovement,
)
from app.models.hr import LeaveRequest, LeaveType, Payroll  # noqa: F401
from app.models.library import (  # noqa: F401
    BookIssue,
    LibraryAcquisitionRequest,
    LibraryBook,
    LibraryBookCopy,
    LibraryGoodsReceipt,
    LibraryGoodsReceiptLine,
    LibraryPurchaseOrder,
    LibraryPurchaseOrderLine,
)
from app.models.people import (  # noqa: F401
    Employee,
    Guardian,
    Student,
    Teacher,
    TeacherAssignment,
    TeacherProfile,
)
from app.models.student_records import (  # noqa: F401
    Achievement,
    DisciplinaryAction,
    StudentAcademicHistory,
    StudentRemark,
)
from app.models.tenant import Campus, Institution, Tenant  # noqa: F401
from app.models.transport import (  # noqa: F401
    RouteStop,
    StudentTransportAssignment,
    TransportRoute,
    Vehicle,
)

__all__ = [
    "AcademicYear", "Grade", "Program", "Section", "Semester", "Subject", "Topic",
    "AdmissionLead", "AdmissionApplicant", "AdmissionApplication", "AdmissionCharge",
    "AdmissionDocument", "AdmissionVerification", "Attendance",
    "Permission", "Role", "RolePermission", "User", "UserRole",
    "Exam", "ExamSubject", "Marks", "MarksBatch", "QuestionPaper",
    "FeePlan", "FeePlanComponent", "Invoice", "Payment",
    "AuditLog", "Document", "EntityDef", "EntityRecord", "FieldDef", "MasterType",
    "MasterValue", "MenuItem", "Module", "ModuleCapability", "Notification", "Setting",
    "Employee", "Guardian", "Student", "Teacher", "TeacherAssignment", "TeacherProfile",
    "Campus", "Institution", "Tenant",
    "LibraryBook", "LibraryBookCopy", "BookIssue", "LibraryAcquisitionRequest",
    "LibraryPurchaseOrder", "LibraryPurchaseOrderLine", "LibraryGoodsReceipt",
    "LibraryGoodsReceiptLine",
    "TransportRoute", "Vehicle", "RouteStop", "StudentTransportAssignment",
    "HostelBlock", "HostelRoom", "HostelAllocation", "HostelBed",
    "HostelAttendance", "HostelVisitor", "HostelIncident",
    "LeaveType", "LeaveRequest", "Payroll",
    "Homework", "HomeworkSubmission", "TimetablePeriod", "LessonPlan", "CurriculumPlan",
    "LedgerAccount", "Vendor", "Expense", "PurchaseOrder",
    "InventoryItem", "StockMovement", "AssetAssignment", "Activity", "ActivityRegistration",
    "MealPlan", "MealMenu", "Announcement", "CmsPage", "Banner",
    "LearningResource", "KnowledgeArticle", "QuestionBankItem", "PtmMeeting",
    "StudentAcademicHistory", "Achievement", "DisciplinaryAction", "StudentRemark",
]
