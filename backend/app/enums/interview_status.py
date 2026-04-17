import enum
class InterviewStatus(str, enum.Enum):
	PENDING = "PENDING"
	IN_PROGRESS = "IN_PROGRESS"
	COMPLETED = "COMPLETED"


if __name__ == "__main__":
    print(InterviewStatus.PENDING)
    print(InterviewStatus.IN_PROGRESS)
    print(InterviewStatus.COMPLETED)