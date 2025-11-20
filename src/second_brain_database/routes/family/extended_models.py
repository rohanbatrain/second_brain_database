"""
Family Hub extended features models for photos, shopping, meals, chores, goals, and tokens.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# PHOTO ALBUM MODELS
# ============================================================================

class PhotoUploadResponse(BaseModel):
    """Response model for photo upload."""
    photo_id: str
    family_id: str
    url: str
    caption: Optional[str]
    uploaded_by: str
    uploaded_by_name: Optional[str]
    uploaded_at: datetime


class PhotoListResponse(BaseModel):
    """Response model for photo list."""
    photos: List[PhotoUploadResponse]
    total_count: int


# ============================================================================
# SHOPPING LIST MODELS
# ============================================================================

class ShoppingListItemCreate(BaseModel):
    """Request model for creating a shopping list item."""
    name: str = Field(..., min_length=1, max_length=200)
    quantity: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    assigned_to: Optional[str] = None


class ShoppingListCreate(BaseModel):
    """Request model for creating a shopping list."""
    name: str = Field(..., min_length=1, max_length=200)
    family_id: str
    items: List[ShoppingListItemCreate] = []


class ShoppingListItemResponse(BaseModel):
    """Response model for shopping list item."""
    item_id: str
    name: str
    quantity: Optional[str]
    category: Optional[str]
    checked: bool
    assigned_to: Optional[str]
    assigned_to_name: Optional[str]
    created_at: datetime


class ShoppingListResponse(BaseModel):
    """Response model for shopping list."""
    list_id: str
    family_id: str
    name: str
    items: List[ShoppingListItemResponse]
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


# ============================================================================
# MEAL PLANNING MODELS
# ============================================================================

class MealPlanCreate(BaseModel):
    """Request model for creating a meal plan."""
    family_id: str
    date: datetime
    meal_type: str = Field(..., pattern="^(breakfast|lunch|dinner|snack)$")
    recipe_name: str = Field(..., min_length=1, max_length=200)
    ingredients: Optional[List[str]] = []
    notes: Optional[str] = Field(None, max_length=1000)


class MealPlanResponse(BaseModel):
    """Response model for meal plan."""
    plan_id: str
    family_id: str
    date: datetime
    meal_type: str
    recipe_name: str
    ingredients: Optional[List[str]]
    notes: Optional[str]
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime


# ============================================================================
# CHORE ROTATION MODELS
# ============================================================================

class ChoreRotationCreate(BaseModel):
    """Request model for creating a chore rotation."""
    family_id: str
    chore_name: str = Field(..., min_length=1, max_length=200)
    rotation_schedule: str = Field(..., pattern="^(daily|weekly|biweekly|monthly)$")
    assigned_members: List[str]  # List of user IDs
    reward_amount: Optional[int] = Field(0, ge=0)


class ChoreRotationResponse(BaseModel):
    """Response model for chore rotation."""
    rotation_id: str
    family_id: str
    chore_name: str
    rotation_schedule: str
    assigned_members: List[dict]  # List of {user_id, username}
    current_assignee: Optional[str]
    current_assignee_name: Optional[str]
    next_rotation_date: datetime
    reward_amount: int
    created_at: datetime


# ============================================================================
# FAMILY GOALS MODELS
# ============================================================================

class FamilyGoalCreate(BaseModel):
    """Request model for creating a family goal."""
    family_id: str
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    target_date: Optional[datetime] = None
    goal_type: str = Field(..., pattern="^(individual|family)$")
    assigned_to: Optional[str] = None  # For individual goals
    milestones: List[str] = []


class FamilyGoalUpdate(BaseModel):
    """Request model for updating a family goal."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    progress: Optional[int] = Field(None, ge=0, le=100)
    completed_milestones: Optional[List[str]] = None


class FamilyGoalResponse(BaseModel):
    """Response model for family goal."""
    goal_id: str
    family_id: str
    title: str
    description: Optional[str]
    target_date: Optional[datetime]
    goal_type: str
    assigned_to: Optional[str]
    assigned_to_name: Optional[str]
    milestones: List[str]
    completed_milestones: List[str]
    progress: int  # 0-100
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


# ============================================================================
# TOKEN SYSTEM MODELS
# ============================================================================

class TokenRuleCreate(BaseModel):
    """Request model for creating a token earning rule."""
    family_id: str
    rule_name: str = Field(..., min_length=1, max_length=200)
    rule_type: str = Field(..., pattern="^(task_completion|chore_completion|goal_achievement|custom)$")
    token_amount: int = Field(..., ge=1)
    conditions: Optional[dict] = {}


class TokenRuleResponse(BaseModel):
    """Response model for token earning rule."""
    rule_id: str
    family_id: str
    rule_name: str
    rule_type: str
    token_amount: int
    conditions: Optional[dict]
    active: bool
    created_at: datetime


class RewardCreate(BaseModel):
    """Request model for creating a reward."""
    family_id: str
    reward_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    token_cost: int = Field(..., ge=1)
    category: Optional[str] = Field(None, max_length=100)
    quantity_available: Optional[int] = Field(None, ge=0)


class RewardResponse(BaseModel):
    """Response model for reward."""
    reward_id: str
    family_id: str
    reward_name: str
    description: Optional[str]
    token_cost: int
    category: Optional[str]
    quantity_available: Optional[int]
    quantity_claimed: int
    created_at: datetime


class TokenTransactionResponse(BaseModel):
    """Response model for token transaction."""
    transaction_id: str
    family_id: str
    user_id: str
    username: Optional[str]
    transaction_type: str  # earned, spent, transfer, allowance
    amount: int
    description: Optional[str]
    related_id: Optional[str]  # task_id, reward_id, etc.
    created_at: datetime


class AllowanceScheduleCreate(BaseModel):
    """Request model for creating an allowance schedule."""
    family_id: str
    recipient_id: str
    amount: int = Field(..., ge=1)
    frequency: str = Field(..., pattern="^(daily|weekly|monthly)$")
    active: bool = True


class AllowanceScheduleResponse(BaseModel):
    """Response model for allowance schedule."""
    schedule_id: str
    family_id: str
    recipient_id: str
    recipient_name: Optional[str]
    amount: int
    frequency: str
    active: bool
    last_distributed: Optional[datetime]
    next_distribution: datetime
    created_at: datetime
