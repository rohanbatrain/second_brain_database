"""Message vote manager for chat system."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase


class MessageVoteManager:
    """Manager for handling message votes and vote statistics."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with database connection.

        Args:
            db: AsyncIOMotor database instance
        """
        self.db = db
        self.votes_collection = db.message_votes
        self.messages_collection = db.chat_messages

    async def vote_message(
        self, message_id: str, user_id: str, vote_type: str
    ) -> Dict:
        """Create or update a vote for a message.

        Args:
            message_id: ID of the message to vote on
            user_id: ID of the user voting
            vote_type: Type of vote ("up" or "down")

        Returns:
            Dictionary containing the vote information

        Raises:
            ValueError: If vote_type is not "up" or "down"
        """
        # Validate vote type
        if vote_type not in ["up", "down"]:
            raise ValueError(f"Invalid vote_type: {vote_type}. Must be 'up' or 'down'")

        # Check if vote already exists
        existing_vote = await self.votes_collection.find_one(
            {"message_id": message_id, "user_id": user_id}
        )

        now = datetime.utcnow()

        if existing_vote:
            # Update existing vote
            await self.votes_collection.update_one(
                {"message_id": message_id, "user_id": user_id},
                {"$set": {"vote_type": vote_type, "updated_at": now}},
            )

            return {
                "id": existing_vote["id"],
                "message_id": message_id,
                "user_id": user_id,
                "vote_type": vote_type,
                "created_at": existing_vote["created_at"],
                "updated_at": now,
                "is_new": False,
            }
        else:
            # Create new vote
            vote_id = str(uuid4())
            vote_doc = {
                "id": vote_id,
                "message_id": message_id,
                "user_id": user_id,
                "vote_type": vote_type,
                "created_at": now,
                "updated_at": now,
            }

            await self.votes_collection.insert_one(vote_doc)

            return {
                "id": vote_id,
                "message_id": message_id,
                "user_id": user_id,
                "vote_type": vote_type,
                "created_at": now,
                "updated_at": now,
                "is_new": True,
            }

    async def get_votes_for_session(self, session_id: str) -> List[Dict]:
        """Get all votes for messages in a session using aggregation.

        Args:
            session_id: ID of the chat session

        Returns:
            List of vote documents with message information
        """
        # Use aggregation pipeline to join messages and votes
        pipeline = [
            # Match messages in the session
            {"$match": {"session_id": session_id}},
            # Lookup votes for each message
            {
                "$lookup": {
                    "from": "message_votes",
                    "localField": "id",
                    "foreignField": "message_id",
                    "as": "votes",
                }
            },
            # Unwind votes array (creates one document per vote)
            {"$unwind": {"path": "$votes", "preserveNullAndEmptyArrays": False}},
            # Project only needed fields
            {
                "$project": {
                    "_id": 0,
                    "vote_id": "$votes.id",
                    "message_id": "$id",
                    "user_id": "$votes.user_id",
                    "vote_type": "$votes.vote_type",
                    "created_at": "$votes.created_at",
                    "updated_at": "$votes.updated_at",
                    "message_content": "$content",
                    "message_role": "$role",
                }
            },
            # Sort by creation time
            {"$sort": {"created_at": 1}},
        ]

        votes = await self.messages_collection.aggregate(pipeline).to_list(None)
        return votes

    async def get_vote_statistics(self, message_id: str) -> Dict:
        """Calculate vote statistics for a message.

        Args:
            message_id: ID of the message

        Returns:
            Dictionary containing vote statistics:
            - upvotes: Number of upvotes
            - downvotes: Number of downvotes
            - score: Net score (upvotes - downvotes)
            - total_votes: Total number of votes
        """
        # Get all votes for the message
        votes = await self.votes_collection.find({"message_id": message_id}).to_list(
            None
        )

        upvotes = sum(1 for v in votes if v["vote_type"] == "up")
        downvotes = sum(1 for v in votes if v["vote_type"] == "down")
        score = upvotes - downvotes
        total_votes = len(votes)

        return {
            "message_id": message_id,
            "upvotes": upvotes,
            "downvotes": downvotes,
            "score": score,
            "total_votes": total_votes,
        }

    async def get_user_vote(
        self, message_id: str, user_id: str
    ) -> Optional[Dict]:
        """Get a specific user's vote for a message.

        Args:
            message_id: ID of the message
            user_id: ID of the user

        Returns:
            Vote document if exists, None otherwise
        """
        vote = await self.votes_collection.find_one(
            {"message_id": message_id, "user_id": user_id}
        )

        if vote:
            # Remove MongoDB _id field
            vote.pop("_id", None)

        return vote

    async def delete_vote(self, message_id: str, user_id: str) -> bool:
        """Delete a user's vote for a message.

        Args:
            message_id: ID of the message
            user_id: ID of the user

        Returns:
            True if vote was deleted, False if no vote existed
        """
        result = await self.votes_collection.delete_one(
            {"message_id": message_id, "user_id": user_id}
        )

        return result.deleted_count > 0
