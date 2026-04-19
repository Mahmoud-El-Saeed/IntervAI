import enum
class InterviewStatus(str, enum.Enum):
	PENDING = "PENDING"
	IN_PROGRESS = "IN_PROGRESS"
	COMPLETED = "COMPLETED"
