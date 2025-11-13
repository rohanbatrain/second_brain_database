"""
Comprehensive unit tests for the SkillManager class.

Tests all CRUD operations, hierarchy management, analytics computation,
error handling, and edge cases.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import ValidationError

from second_brain_database.managers.skill_manager import (
    SkillError,
    SkillHierarchyError,
    SkillManager,
    SkillNotFoundError,
    SkillValidationError,
)
from second_brain_database.models.skill_models import (
    CreateSkillLogRequest,
    CreateSkillRequest,
    SkillDocument,
    SkillLogDocument,
    SkillMetadata,
    SkillLogContext,
    UpdateSkillRequest,
)


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing."""
    db_manager = AsyncMock()
    collection = AsyncMock(spec=AsyncIOMotorCollection)
    
    # Configure async methods to return proper values
    collection.find_one = AsyncMock()
    collection.insert_one = AsyncMock()
    collection.update_one = AsyncMock()
    collection.count_documents = AsyncMock()
    collection.find = MagicMock()  # This returns a mock cursor
    collection.delete_one = AsyncMock()
    
    db_manager.get_collection.return_value = collection
    return db_manager


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    return AsyncMock()


@pytest.fixture
def skill_manager(mock_db_manager, mock_logger):
    """Create SkillManager instance with mocked dependencies."""
    manager = SkillManager(db_manager=mock_db_manager, logging_manager=mock_logger)
    # Set the collection directly to avoid lazy loading
    manager._collection = mock_db_manager.get_collection.return_value
    return manager


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing."""
    db_manager = AsyncMock()
    collection = AsyncMock(spec=AsyncIOMotorCollection)
    db_manager.get_collection.return_value = collection
    return db_manager


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    return AsyncMock()


@pytest.fixture
def skill_manager(mock_db_manager, mock_logger):
    """Create SkillManager instance with mocked dependencies."""
    manager = SkillManager(db_manager=mock_db_manager, logging_manager=mock_logger)
    # Set the collection directly to avoid lazy loading
    manager._collection = mock_db_manager.get_collection.return_value
    return manager


@pytest.fixture
def sample_skill_data():
    """Sample skill data for testing."""
    return {
        "skill_id": str(uuid.uuid4()),
        "user_id": "test_user_123",
        "name": "Python Programming",
        "description": "Learning Python programming language",
        "parent_skill_ids": [],
        "tags": ["programming", "python"],
        "metadata": SkillMetadata(category="programming", difficulty="intermediate"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True,
        "logs": []
    }


@pytest.fixture
def sample_skill_doc(sample_skill_data):
    """Sample SkillDocument for testing."""
    return SkillDocument(**sample_skill_data)


@pytest.fixture
def sample_log_data():
    """Sample log data for testing."""
    return {
        "log_id": str(uuid.uuid4()),
        "project_id": "project_123",
        "progress_state": "learning",
        "numeric_level": 2,
        "timestamp": datetime.utcnow(),
        "notes": "Made good progress today",
        "context": SkillLogContext(duration_hours=2.5, confidence_level=7),
        "created_at": datetime.utcnow()
    }


@pytest.fixture
def sample_log_doc(sample_log_data):
    """Sample SkillLogDocument for testing."""
    return SkillLogDocument(**sample_log_data)


class TestSkillManagerInitialization:
    """Test SkillManager initialization and setup."""

    def test_initialization_with_dependencies(self, mock_db_manager, mock_logger):
        """Test that SkillManager initializes correctly with provided dependencies."""
        manager = SkillManager(db_manager=mock_db_manager, logging_manager=mock_logger)
        assert manager.db_manager == mock_db_manager
        assert manager.logging_manager == mock_logger

    def test_collection_lazy_loading(self, mock_db_manager, mock_logger):
        """Test that collection is loaded lazily."""
        manager = SkillManager(db_manager=mock_db_manager, logging_manager=mock_logger)
        # Collection should not be accessed yet
        mock_db_manager.get_collection.assert_not_called()

        # Access collection property
        collection = manager.collection
        mock_db_manager.get_collection.assert_called_once_with("user_skills")
        assert collection == mock_db_manager.get_collection.return_value

    def test_collection_caching(self, mock_db_manager, mock_logger):
        """Test that collection is cached after first access."""
        manager = SkillManager(db_manager=mock_db_manager, logging_manager=mock_logger)

        # First access
        collection1 = manager.collection
        # Second access should use cached value
        collection2 = manager.collection

        # get_collection should only be called once
        mock_db_manager.get_collection.assert_called_once_with("user_skills")
        assert collection1 is collection2


class TestSkillValidation:
    """Test skill validation and ownership checks."""

    @pytest.mark.asyncio
    async def test_validate_skill_ownership_success(self, skill_manager, sample_skill_data):
        """Test successful skill ownership validation."""
        skill_manager.collection.find_one.return_value = sample_skill_data

        result = await skill_manager._validate_skill_ownership(
            sample_skill_data["skill_id"], sample_skill_data["user_id"]
        )

        assert isinstance(result, SkillDocument)
        assert result.skill_id == sample_skill_data["skill_id"]
        skill_manager.collection.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_skill_ownership_not_found(self, skill_manager):
        """Test skill ownership validation when skill doesn't exist."""
        skill_manager.collection.find_one.return_value = None

        with pytest.raises(SkillNotFoundError) as exc_info:
            await skill_manager._validate_skill_ownership("nonexistent_id", "user_123")

        assert exc_info.value.skill_id == "nonexistent_id"
        assert exc_info.value.user_id == "user_123"

    @pytest.mark.asyncio
    async def test_validate_skill_ownership_invalid_data(self, skill_manager):
        """Test skill ownership validation with invalid document data."""
        skill_manager.collection.find_one.return_value = {"invalid": "data"}

        with pytest.raises(SkillValidationError):
            await skill_manager._validate_skill_ownership("skill_id", "user_id")


class TestCircularReferenceDetection:
    """Test circular reference detection in skill hierarchies."""

    @pytest.mark.asyncio
    async def test_detect_circular_reference_no_cycle(self, skill_manager):
        """Test circular reference detection with no cycles."""
        # Mock empty parent chain
        skill_manager.collection.find_one.return_value = {"parent_skill_ids": []}

        result = await skill_manager._detect_circular_reference("skill_a", "skill_b", "user_123")
        assert result is False

    @pytest.mark.asyncio
    async def test_detect_circular_reference_direct_cycle(self, skill_manager):
        """Test circular reference detection with direct self-reference."""
        result = await skill_manager._detect_circular_reference("skill_a", "skill_a", "user_123")
        assert result is True

    @pytest.mark.asyncio
    async def test_detect_circular_reference_indirect_cycle(self, skill_manager):
        """Test circular reference detection with indirect cycles."""
        # Mock a chain that leads back to the original skill
        skill_manager.collection.find_one.side_effect = [
            {"parent_skill_ids": ["skill_c"]},  # skill_b -> skill_c
            {"parent_skill_ids": ["skill_a"]},  # skill_c -> skill_a (cycle!)
        ]

        result = await skill_manager._detect_circular_reference("skill_a", "skill_b", "user_123")
        assert result is True


class TestSkillCreation:
    """Test skill creation functionality."""

    @pytest.mark.asyncio
    async def test_create_skill_success(self, skill_manager, mock_logger):
        """Test successful skill creation."""
        request = CreateSkillRequest(
            name="Test Skill",
            description="A test skill",
            tags=["test", "skill"],
            metadata=SkillMetadata(category="testing")
        )

        # Mock successful insertion
        skill_manager.collection.insert_one.return_value = AsyncMock()

        result = await skill_manager.create_skill(request, "user_123")

        assert isinstance(result, SkillDocument)
        assert result.name == "Test Skill"
        assert result.user_id == "user_123"
        assert result.is_active is True
        assert len(result.parent_skill_ids) == 0

        # Verify logging
        mock_logger.info.assert_called()

        # Verify database insertion
        skill_manager.collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_skill_with_parent_validation(self, skill_manager, sample_skill_data):
        """Test skill creation with parent skill validation."""
        # Mock parent skill exists
        skill_manager.collection.find_one.return_value = sample_skill_data

        request = CreateSkillRequest(
            name="Child Skill",
            parent_skill_ids=[sample_skill_data["skill_id"]]
        )

        skill_manager.collection.insert_one.return_value = AsyncMock()

        result = await skill_manager.create_skill(request, "user_123")

        assert result.parent_skill_ids == [sample_skill_data["skill_id"]]

    @pytest.mark.asyncio
    async def test_create_skill_parent_not_found(self, skill_manager):
        """Test skill creation fails when parent doesn't exist."""
        skill_manager.collection.find_one.return_value = None

        request = CreateSkillRequest(
            name="Child Skill",
            parent_skill_ids=["nonexistent_parent"]
        )

        with pytest.raises(SkillNotFoundError):
            await skill_manager.create_skill(request, "user_123")

    @pytest.mark.asyncio
    async def test_create_skill_circular_reference(self, skill_manager):
        """Test skill creation fails with circular reference."""
        # Mock circular reference detection
        with patch.object(skill_manager, '_detect_circular_reference', return_value=True):
            request = CreateSkillRequest(
                name="Circular Skill",
                parent_skill_ids=["parent_id"]
            )

            with pytest.raises(SkillHierarchyError) as exc_info:
                await skill_manager.create_skill(request, "user_123")

            assert "circular reference" in str(exc_info.value)


class TestSkillRetrieval:
    """Test skill retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_skill_basic(self, skill_manager, sample_skill_data):
        """Test basic skill retrieval."""
        skill_manager.collection.find_one.return_value = sample_skill_data

        result = await skill_manager.get_skill(sample_skill_data["skill_id"], sample_skill_data["user_id"])

        assert result["skill_id"] == sample_skill_data["skill_id"]
        assert result["name"] == sample_skill_data["name"]
        assert "child_skill_ids" in result

    @pytest.mark.asyncio
    async def test_get_skill_with_analytics(self, skill_manager, sample_skill_data):
        """Test skill retrieval with analytics."""
        skill_manager.collection.find_one.return_value = sample_skill_data

        with patch.object(skill_manager, '_compute_skill_analytics') as mock_compute:
            mock_compute.return_value = {"total_logs": 5, "current_state": "learning"}

            result = await skill_manager.get_skill(
                sample_skill_data["skill_id"],
                sample_skill_data["user_id"],
                include_analytics=True
            )

            assert "analytics" in result
            mock_compute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_skills_basic(self, skill_manager, sample_skill_data):
        """Test basic skill listing."""
        # Mock count and find operations
        skill_manager.collection.count_documents.return_value = 1
        skill_manager.collection.find.return_value = [sample_skill_data]

        result = await skill_manager.list_skills("user_123")

        assert result["total_count"] == 1
        assert len(result["skills"]) == 1
        assert result["skills"][0]["skill_id"] == sample_skill_data["skill_id"]


class TestSkillHierarchy:
    """Test skill hierarchy management."""

    @pytest.mark.asyncio
    async def test_link_parent_skill_success(self, skill_manager, sample_skill_data):
        """Test successful parent skill linking."""
        # Mock skills exist
        skill_manager.collection.find_one.return_value = sample_skill_data
        skill_manager.collection.update_one.return_value = AsyncMock(modified_count=1)

        result = await skill_manager.link_parent_skill(
            sample_skill_data["skill_id"], "parent_id", sample_skill_data["user_id"]
        )

        assert result is True
        skill_manager.collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_parent_skill_self_reference(self, skill_manager, sample_skill_data):
        """Test linking skill to itself fails."""
        skill_manager.collection.find_one.return_value = sample_skill_data

        with pytest.raises(SkillHierarchyError) as exc_info:
            await skill_manager.link_parent_skill(
                "same_id", "same_id", sample_skill_data["user_id"]
            )

        assert "Cannot link skill to itself" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unlink_parent_skill_success(self, skill_manager):
        """Test successful parent skill unlinking."""
        skill_manager.collection.update_one.return_value = AsyncMock(modified_count=1)

        result = await skill_manager.unlink_parent_skill("skill_id", "parent_id", "user_id")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_skill_tree(self, skill_manager):
        """Test skill tree retrieval."""
        # Mock skills data
        skills_data = [
            {"skill_id": "root", "name": "Root Skill", "parent_skill_ids": []},
            {"skill_id": "child", "name": "Child Skill", "parent_skill_ids": ["root"]},
        ]

        skill_manager.collection.find.return_value = skills_data

        result = await skill_manager.get_skill_tree("user_123")

        assert len(result) == 1  # One root skill
        assert result[0]["skill_id"] == "root"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["skill_id"] == "child"


class TestSkillLogs:
    """Test skill log operations."""

    @pytest.mark.asyncio
    async def test_add_skill_log_success(self, skill_manager, sample_skill_data, sample_log_data):
        """Test successful skill log addition."""
        skill_manager.collection.find_one.return_value = sample_skill_data
        skill_manager.collection.update_one.return_value = AsyncMock(modified_count=1)

        request = CreateSkillLogRequest(
            progress_state="learning",
            notes="Test log entry",
            context=SkillLogContext(duration_hours=1.5)
        )

        result = await skill_manager.add_skill_log(sample_skill_data["skill_id"], request, "user_123")

        assert isinstance(result, SkillLogDocument)
        assert result.progress_state == "learning"
        assert result.notes == "Test log entry"

    @pytest.mark.asyncio
    async def test_get_skill_logs(self, skill_manager, sample_skill_data, sample_log_data):
        """Test skill log retrieval."""
        sample_skill_data["logs"] = [sample_log_data]
        skill_manager.collection.find_one.return_value = sample_skill_data

        result = await skill_manager.get_skill_logs(sample_skill_data["skill_id"], "user_123")

        assert len(result) == 1
        assert result[0]["log_id"] == sample_log_data["log_id"]

    @pytest.mark.asyncio
    async def test_update_skill_log_success(self, skill_manager):
        """Test successful skill log update."""
        skill_manager.collection.update_one.return_value = AsyncMock(modified_count=1)

        result = await skill_manager.update_skill_log(
            "skill_id", "log_id", {"notes": "Updated notes"}, "user_id"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_skill_log_success(self, skill_manager):
        """Test successful skill log deletion."""
        skill_manager.collection.update_one.return_value = AsyncMock(modified_count=1)

        result = await skill_manager.delete_skill_log("skill_id", "log_id", "user_id")

        assert result is True


class TestAnalytics:
    """Test analytics computation."""

    @pytest.mark.asyncio
    async def test_compute_skill_analytics_basic(self, skill_manager, sample_skill_data, sample_log_data):
        """Test basic skill analytics computation."""
        sample_skill_data["logs"] = [sample_log_data]
        skill_manager.collection.find_one.return_value = sample_skill_data

        result = await skill_manager._compute_skill_analytics("skill_id", "user_id")

        assert result.total_logs == 1
        assert result.current_state == "learning"
        assert result.total_hours == 2.5  # from sample_log_data context

    @pytest.mark.asyncio
    async def test_get_analytics_summary(self, skill_manager, sample_skill_data):
        """Test comprehensive analytics summary."""
        # Mock skills with logs
        sample_skill_data["logs"] = [
            {"timestamp": datetime.utcnow().isoformat(), "progress_state": "learning"}
        ]

        skill_manager.collection.find.return_value = [sample_skill_data]

        result = await skill_manager.get_analytics_summary("user_123")

        assert "total_skills" in result
        assert "active_skills" in result
        assert "skills_by_state" in result
        assert "recent_activity" in result
        assert "stale_skills" in result


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_delete_skill_with_children_fails(self, skill_manager):
        """Test that deleting a skill with children fails."""
        # Mock children exist
        skill_manager.collection.count_documents.return_value = 2

        with pytest.raises(SkillHierarchyError) as exc_info:
            await skill_manager.delete_skill("skill_id", "user_id")

        assert "child skills" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_skill_not_found(self, skill_manager):
        """Test updating non-existent skill."""
        skill_manager.collection.find_one.return_value = None

        request = UpdateSkillRequest(name="New Name")

        with pytest.raises(SkillNotFoundError):
            await skill_manager.update_skill("nonexistent", request, "user_id")

    @pytest.mark.asyncio
    async def test_database_operation_failure(self, skill_manager):
        """Test handling of database operation failures."""
        skill_manager.collection.insert_one.side_effect = Exception("Database error")

        request = CreateSkillRequest(name="Test Skill")

        with pytest.raises(SkillError) as exc_info:
            await skill_manager.create_skill(request, "user_id")

        assert "Failed to create skill" in str(exc_info.value)


class TestConcurrency:
    """Test concurrent operations and race conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_skill_creation(self, skill_manager):
        """Test concurrent skill creation doesn't cause issues."""
        request = CreateSkillRequest(name="Concurrent Skill")

        # Mock successful operations
        skill_manager.collection.insert_one.return_value = AsyncMock()

        # Create multiple skills concurrently
        tasks = [
            skill_manager.create_skill(request, "user_123")
            for _ in range(3)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, SkillDocument)
            assert result.name == "Concurrent Skill"