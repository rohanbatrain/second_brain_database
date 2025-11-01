"""
Commerce Agent

This agent specializes in shopping assistance using existing
shop and asset systems.

Capabilities:
- Intelligent shopping recommendations based on user preferences
- Asset management and rental tracking
- Budget planning and SBD token management
- Deal notifications and personalized offers
- Purchase history analysis and insights
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from .base_agent import BaseAgent
from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext
from ....managers.logging_manager import get_logger

logger = get_logger(prefix="[CommerceAgent]")


class CommerceAgent(BaseAgent):
    """
    AI agent specialized in shopping assistance and commerce operations.
    
    Integrates with existing shop_tools MCP tools and SBD token systems
    to provide natural language interface for shopping and asset management.
    """
    
    def __init__(self, orchestrator=None):
        super().__init__("commerce", orchestrator)
        self.capabilities = [
            {
                "name": "shopping_recommendations",
                "description": "Provide personalized shopping recommendations",
                "required_permissions": ["shop:browse"]
            },
            {
                "name": "asset_management",
                "description": "Manage digital assets and rentals",
                "required_permissions": ["assets:manage"]
            },
            {
                "name": "budget_planning",
                "description": "Help with budget planning and SBD token management",
                "required_permissions": ["tokens:view"]
            },
            {
                "name": "purchase_assistance",
                "description": "Assist with purchases and transactions",
                "required_permissions": ["shop:purchase"]
            },
            {
                "name": "deal_notifications",
                "description": "Notify about deals and special offers",
                "required_permissions": ["shop:browse"]
            }
        ]
    
    @property
    def agent_name(self) -> str:
        return "Shopping & Commerce Assistant"
    
    @property
    def agent_description(self) -> str:
        return "I help you find the perfect digital assets, manage your purchases, plan your budget, and discover great deals in the shop."
    
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle commerce-related requests with streaming responses."""
        try:
            # Add request to conversation history
            self.add_to_conversation_history(session_id, "user", request)
            
            # Classify the commerce task
            task_classification = await self.classify_commerce_task(request)
            task_type = task_classification.get("task_type", "general")
            
            self.logger.info(
                "Processing commerce request for session %s: %s (classified as %s)",
                session_id, request[:100], task_type
            )
            
            # Route to appropriate commerce operation
            if task_type == "browse_shop":
                async for event in self.browse_shop_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "purchase_item":
                async for event in self.purchase_item_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "recommendations":
                async for event in self.recommendations_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "budget_planning":
                async for event in self.budget_planning_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "purchase_history":
                async for event in self.purchase_history_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "asset_management":
                async for event in self.asset_management_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "deals_offers":
                async for event in self.deals_offers_workflow(session_id, request, user_context):
                    yield event
            else:
                # General commerce assistance
                async for event in self.general_commerce_assistance(session_id, request, user_context):
                    yield event
                    
        except Exception as e:
            self.logger.error("Commerce request handling failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue processing your shopping request: {str(e)}")
    
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """Get commerce capabilities available to the user."""
        available_capabilities = []
        
        for capability in self.capabilities:
            required_perms = capability.get("required_permissions", [])
            if await self.validate_permissions(user_context, required_perms):
                available_capabilities.append(capability)
        
        return available_capabilities
    
    async def classify_commerce_task(self, request: str) -> Dict[str, Any]:
        """Classify the type of commerce task from the request."""
        request_lower = request.lower()
        
        # Browse shop patterns
        if any(phrase in request_lower for phrase in [
            "browse shop", "show items", "what's available", "shop catalog", "browse store"
        ]):
            return {"task_type": "browse_shop", "confidence": 0.9}
        
        # Purchase patterns
        if any(phrase in request_lower for phrase in [
            "buy", "purchase", "get this", "i want", "add to cart"
        ]):
            return {"task_type": "purchase_item", "confidence": 0.9}
        
        # Recommendations patterns
        if any(phrase in request_lower for phrase in [
            "recommend", "suggest", "what should i", "help me choose", "best for me"
        ]):
            return {"task_type": "recommendations", "confidence": 0.8}
        
        # Budget planning patterns
        if any(phrase in request_lower for phrase in [
            "budget", "afford", "how much", "token balance", "spending plan"
        ]):
            return {"task_type": "budget_planning", "confidence": 0.8}
        
        # Purchase history patterns
        if any(phrase in request_lower for phrase in [
            "purchase history", "what i bought", "my purchases", "order history"
        ]):
            return {"task_type": "purchase_history", "confidence": 0.9}
        
        # Asset management patterns
        if any(phrase in request_lower for phrase in [
            "my assets", "manage items", "my collection", "owned items"
        ]):
            return {"task_type": "asset_management", "confidence": 0.8}
        
        # Deals and offers patterns
        if any(phrase in request_lower for phrase in [
            "deals", "offers", "discounts", "sales", "special price"
        ]):
            return {"task_type": "deals_offers", "confidence": 0.8}
        
        return {"task_type": "general", "confidence": 0.5}
    
    async def browse_shop_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle shop browsing workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Browsing the shop for you...")
        
        try:
            # Extract item type and filters from request
            item_type = await self.extract_item_type(request)
            price_range = await self.extract_price_range(request)
            
            # Get shop items using MCP tool
            params = {"user_id": user_context.user_id}
            if item_type:
                params["item_type"] = item_type
            if price_range:
                params.update(price_range)
            
            result = await self.execute_mcp_tool(
                session_id,
                "browse_shop_items",
                params,
                user_context
            )
            
            if result and not result.get("error"):
                items = result.get("items", [])
                
                if items:
                    response = f"**Shop Items"
                    if item_type:
                        response += f" - {item_type.title()}s"
                    response += f" ({len(items)} found):**\n\n"
                    
                    for i, item in enumerate(items[:10], 1):  # Show first 10 items
                        name = item.get("name", "Unknown Item")
                        price = item.get("price", 0)
                        item_type_display = item.get("type", "item")
                        description = item.get("description", "")
                        
                        response += f"**{i}. {name}** ({item_type_display})\n"
                        response += f"   💰 Price: {price} SBD tokens\n"
                        if description:
                            # Truncate long descriptions
                            short_desc = description[:100] + "..." if len(description) > 100 else description
                            response += f"   📝 {short_desc}\n"
                        response += "\n"
                    
                    if len(items) > 10:
                        response += f"... and {len(items) - 10} more items available!\n\n"
                    
                    response += "Would you like me to help you purchase any of these items or get more details about a specific one?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    filter_text = f" matching your criteria" if item_type or price_range else ""
                    yield await self.emit_response(
                        session_id,
                        f"I didn't find any items{filter_text} in the shop right now. Check back later for new arrivals!"
                    )
            else:
                yield await self.emit_response(
                    session_id,
                    "I'm having trouble accessing the shop right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Browse shop workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Shop browsing failed: {str(e)}")
    
    async def purchase_item_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle item purchase workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing your purchase request...")
        
        try:
            # Extract item information from request
            item_name = await self.extract_item_name(request)
            
            if not item_name:
                yield await self.emit_response(
                    session_id,
                    "Which item would you like to purchase? Please tell me the name or describe what you're looking for."
                )
                return
            
            # Search for the item first
            search_result = await self.execute_mcp_tool(
                session_id,
                "search_shop_items",
                {
                    "query": item_name,
                    "user_id": user_context.user_id
                },
                user_context
            )
            
            if search_result and not search_result.get("error"):
                items = search_result.get("items", [])
                
                if not items:
                    yield await self.emit_response(
                        session_id,
                        f"I couldn't find an item called '{item_name}' in the shop. Would you like me to show you similar items?"
                    )
                    return
                
                # If multiple items found, ask user to clarify
                if len(items) > 1:
                    response = f"I found {len(items)} items matching '{item_name}':\n\n"
                    for i, item in enumerate(items[:5], 1):
                        name = item.get("name", "Unknown")
                        price = item.get("price", 0)
                        item_type = item.get("type", "item")
                        response += f"{i}. **{name}** ({item_type}) - {price} SBD tokens\n"
                    
                    response += "\nWhich one would you like to purchase? Please tell me the number or exact name."
                    yield await self.emit_response(session_id, response)
                    return
                
                # Single item found, proceed with purchase
                item = items[0]
                item_id = item.get("id")
                item_name = item.get("name")
                item_price = item.get("price", 0)
                
                # Check user's token balance first
                balance_result = await self.execute_mcp_tool(
                    session_id,
                    "get_user_token_balance",
                    {"user_id": user_context.user_id},
                    user_context
                )
                
                if balance_result and not balance_result.get("error"):
                    user_balance = balance_result.get("balance", 0)
                    
                    if user_balance < item_price:
                        yield await self.emit_response(
                            session_id,
                            f"You need {item_price} SBD tokens to purchase '{item_name}', but you only have {user_balance} tokens. Would you like me to help you get more tokens?"
                        )
                        return
                
                # Proceed with purchase
                purchase_result = await self.execute_mcp_tool(
                    session_id,
                    "purchase_shop_item",
                    {
                        "item_id": item_id,
                        "user_id": user_context.user_id
                    },
                    user_context
                )
                
                if purchase_result and not purchase_result.get("error"):
                    new_balance = purchase_result.get("new_balance", 0)
                    response = f"🎉 Congratulations! You've successfully purchased '{item_name}' for {item_price} SBD tokens.\n\n"
                    response += f"💰 Your new token balance: {new_balance} SBD tokens\n\n"
                    response += "The item has been added to your collection. You can use it right away!"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    error_msg = purchase_result.get("error", "Unknown error occurred")
                    yield await self.emit_response(
                        session_id,
                        f"I couldn't complete your purchase: {error_msg}"
                    )
            else:
                yield await self.emit_response(
                    session_id,
                    "I'm having trouble searching the shop right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Purchase workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Purchase failed: {str(e)}")
    
    async def recommendations_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle personalized recommendations workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Finding personalized recommendations for you...")
        
        try:
            # Get personalized recommendations
            result = await self.execute_mcp_tool(
                session_id,
                "get_personalized_recommendations",
                {
                    "user_id": user_context.user_id,
                    "limit": 8
                },
                user_context
            )
            
            if result and not result.get("error"):
                recommendations = result.get("recommendations", [])
                
                if recommendations:
                    response = "**Personalized Recommendations Just for You:**\n\n"
                    
                    for i, item in enumerate(recommendations, 1):
                        name = item.get("name", "Unknown Item")
                        price = item.get("price", 0)
                        item_type = item.get("type", "item")
                        reason = item.get("recommendation_reason", "Popular choice")
                        match_score = item.get("match_score", 0)
                        
                        response += f"**{i}. {name}** ({item_type})\n"
                        response += f"   💰 {price} SBD tokens\n"
                        response += f"   🎯 {reason}\n"
                        response += f"   📊 Match Score: {match_score}%\n\n"
                    
                    response += "These recommendations are based on your preferences, purchase history, and what similar users enjoy. "
                    response += "Would you like more details about any of these items or help with a purchase?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I don't have enough information about your preferences yet to make personalized recommendations. Browse the shop a bit and I'll learn what you like!"
                    )
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't generate recommendations right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Recommendations workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Recommendations failed: {str(e)}")
    
    async def budget_planning_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle budget planning workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Analyzing your budget and spending...")
        
        try:
            # Get user's financial information
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_financial_summary",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                financial_data = result.get("financial_summary", {})
                
                current_balance = financial_data.get("current_balance", 0)
                monthly_spending = financial_data.get("monthly_spending", 0)
                recent_purchases = financial_data.get("recent_purchases", [])
                spending_categories = financial_data.get("spending_by_category", {})
                
                response = "**Your Financial Summary:**\n\n"
                response += f"💰 **Current Balance:** {current_balance} SBD tokens\n"
                response += f"📊 **Monthly Spending:** {monthly_spending} SBD tokens\n\n"
                
                if spending_categories:
                    response += "**Spending by Category:**\n"
                    for category, amount in spending_categories.items():
                        percentage = (amount / monthly_spending * 100) if monthly_spending > 0 else 0
                        response += f"• {category.title()}: {amount} tokens ({percentage:.1f}%)\n"
                    response += "\n"
                
                # Budget recommendations
                if monthly_spending > 0:
                    avg_daily_spending = monthly_spending / 30
                    days_remaining = current_balance / avg_daily_spending if avg_daily_spending > 0 else float('inf')
                    
                    response += "**Budget Insights:**\n"
                    if days_remaining < 30:
                        response += f"⚠️ At your current spending rate, your tokens will last about {days_remaining:.0f} days.\n"
                        response += "Consider reducing spending or earning more tokens.\n"
                    else:
                        response += f"✅ Your current spending rate is sustainable. Tokens will last {days_remaining:.0f}+ days.\n"
                    
                    response += f"\n💡 **Tip:** Try to keep daily spending under {current_balance / 60:.1f} tokens to make your balance last 2 months."
                else:
                    response += "**Budget Status:** You haven't made any purchases recently. Your tokens are safe!"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your financial information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Budget planning workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Budget planning failed: {str(e)}")
    
    async def purchase_history_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle purchase history workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting your purchase history...")
        
        try:
            # Get user's purchase history
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_purchase_history",
                {
                    "user_id": user_context.user_id,
                    "limit": 15
                },
                user_context
            )
            
            if result and not result.get("error"):
                purchases = result.get("purchases", [])
                
                if purchases:
                    total_spent = sum(p.get("price", 0) for p in purchases)
                    
                    response = f"**Your Purchase History ({len(purchases)} recent purchases):**\n\n"
                    
                    for purchase in purchases:
                        item_name = purchase.get("item_name", "Unknown Item")
                        price = purchase.get("price", 0)
                        item_type = purchase.get("item_type", "item")
                        purchase_date = purchase.get("purchase_date", "Unknown date")
                        
                        response += f"• **{item_name}** ({item_type})\n"
                        response += f"  💰 {price} SBD tokens - {purchase_date}\n\n"
                    
                    response += f"**Total Spent:** {total_spent} SBD tokens\n\n"
                    response += "I can help you find similar items or manage your existing purchases. What would you like to do?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "You haven't made any purchases yet. Would you like me to show you what's available in the shop?"
                    )
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your purchase history right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Purchase history workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Purchase history failed: {str(e)}")
    
    async def asset_management_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle asset management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Managing your digital assets...")
        
        try:
            # Get user's assets
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_assets_detailed",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                assets = result.get("assets", {})
                
                response = "**Your Digital Asset Collection:**\n\n"
                
                total_value = 0
                total_items = 0
                
                for asset_type, items in assets.items():
                    if items:
                        response += f"**{asset_type.title()}s ({len(items)}):**\n"
                        
                        for item in items[:5]:  # Show first 5 of each type
                            name = item.get("name", "Unknown")
                            value = item.get("original_price", 0)
                            status = item.get("status", "owned")
                            acquired_date = item.get("acquired_date", "Unknown")
                            
                            status_icon = "✅" if status == "owned" else "🔄" if status == "rented" else "❓"
                            response += f"  {status_icon} {name} (Value: {value} tokens) - {acquired_date}\n"
                            
                            total_value += value
                            total_items += 1
                        
                        if len(items) > 5:
                            response += f"  ... and {len(items) - 5} more {asset_type}s\n"
                        response += "\n"
                
                response += f"**Collection Summary:**\n"
                response += f"📦 Total Items: {total_items}\n"
                response += f"💎 Total Value: {total_value} SBD tokens\n\n"
                response += "I can help you organize your collection, find items to complete sets, or suggest items to sell or trade."
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your asset collection right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Asset management workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Asset management failed: {str(e)}")
    
    async def deals_offers_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle deals and offers workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Finding the best deals for you...")
        
        try:
            # Get current deals and offers
            result = await self.execute_mcp_tool(
                session_id,
                "get_current_deals",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                deals = result.get("deals", [])
                
                if deals:
                    response = "**🔥 Current Deals & Special Offers:**\n\n"
                    
                    for deal in deals:
                        item_name = deal.get("item_name", "Unknown Item")
                        original_price = deal.get("original_price", 0)
                        sale_price = deal.get("sale_price", 0)
                        discount_percent = deal.get("discount_percent", 0)
                        expires_at = deal.get("expires_at", "Unknown")
                        deal_type = deal.get("deal_type", "sale")
                        
                        savings = original_price - sale_price
                        
                        response += f"**{item_name}**\n"
                        response += f"  💰 ~~{original_price}~~ **{sale_price} SBD tokens** ({discount_percent}% off)\n"
                        response += f"  💸 You save: {savings} tokens\n"
                        response += f"  ⏰ Expires: {expires_at}\n"
                        
                        if deal_type == "flash_sale":
                            response += "  ⚡ **Flash Sale!**\n"
                        elif deal_type == "bundle":
                            response += "  📦 **Bundle Deal!**\n"
                        
                        response += "\n"
                    
                    response += "These deals won't last long! Would you like me to help you purchase any of these items?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "There are no special deals available right now, but I'll keep an eye out for you! Check back later for new offers."
                    )
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't check for current deals right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Deals workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Deals lookup failed: {str(e)}")
    
    async def general_commerce_assistance(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle general commerce assistance requests."""
        try:
            # Load user context for personalized response
            context = await self.load_user_context(user_context)
            
            # Emit thinking status
            yield await self.emit_status(session_id, EventType.THINKING, "Loading shopping information...")
            
            # Create a helpful response directly
            response = f"""Hello {context.get('username', 'there')}! I'm your Shopping & Commerce Assistant AI! 🛒

I'm here to make your digital asset shopping experience amazing:

🎨 **Digital Asset Shop**
- Browse avatars, banners, themes, and more
- Search by category, price, or style
- Discover trending and popular items

💡 **Personalized Recommendations**
- Get suggestions based on your preferences
- Find items that match your style
- Discover new collections and artists

💰 **Budget & Planning**
- Check your SBD token balance
- Plan your purchases and spending
- Get budget-friendly recommendations

🎯 **Purchase Assistance**
- Help with buying decisions
- Compare similar items
- Guide you through the purchase process

🔥 **Deals & Offers**
- Find current sales and discounts
- Get notified about special offers
- Discover limited-time deals

📊 **Asset Management**
- Track your digital collection
- Organize your purchased items
- Manage rentals and subscriptions

What kind of shopping help are you looking for today? I can help you find the perfect digital assets!"""

            # Emit the response
            yield await self.emit_response(session_id, response)
            
        except Exception as e:
            self.logger.error("General commerce assistance failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue: {str(e)}")
    
    # Helper methods for extracting information from requests
    
    async def extract_item_type(self, request: str) -> Optional[str]:
        """Extract item type from request text."""
        request_lower = request.lower()
        
        # Common item types
        item_types = ["avatar", "banner", "theme", "background", "icon", "sticker"]
        
        for item_type in item_types:
            if item_type in request_lower or f"{item_type}s" in request_lower:
                return item_type
        
        return None
    
    async def extract_price_range(self, request: str) -> Optional[Dict[str, int]]:
        """Extract price range from request text."""
        import re
        
        # Look for price patterns
        patterns = [
            r'under (\d+)',
            r'less than (\d+)',
            r'below (\d+)',
            r'between (\d+) and (\d+)',
            r'from (\d+) to (\d+)',
            r'(\d+)-(\d+)',
            r'over (\d+)',
            r'more than (\d+)',
            r'above (\d+)'
        ]
        
        request_lower = request.lower()
        
        for pattern in patterns:
            match = re.search(pattern, request_lower)
            if match:
                if "under" in pattern or "less than" in pattern or "below" in pattern:
                    return {"max_price": int(match.group(1))}
                elif "between" in pattern or "from" in pattern or "-" in pattern:
                    return {"min_price": int(match.group(1)), "max_price": int(match.group(2))}
                elif "over" in pattern or "more than" in pattern or "above" in pattern:
                    return {"min_price": int(match.group(1))}
        
        return None
    
    async def extract_item_name(self, request: str) -> Optional[str]:
        """Extract item name from request text."""
        # Look for quoted strings first
        import re
        quoted_pattern = r'["\']([^"\']+)["\']'
        match = re.search(quoted_pattern, request)
        if match:
            return match.group(1)
        
        # Look for patterns like "buy X" or "purchase X"
        buy_patterns = [
            r'buy (?:the )?(.+?)(?:\s|$)',
            r'purchase (?:the )?(.+?)(?:\s|$)',
            r'get (?:the )?(.+?)(?:\s|$)',
            r'want (?:the )?(.+?)(?:\s|$)'
        ]
        
        for pattern in buy_patterns:
            match = re.search(pattern, request.lower())
            if match:
                item_name = match.group(1).strip()
                # Remove common stop words at the end
                stop_words = ["please", "now", "today", "for me"]
                for stop_word in stop_words:
                    if item_name.endswith(stop_word):
                        item_name = item_name[:-len(stop_word)].strip()
                
                if len(item_name) > 2:  # Reasonable item name length
                    return item_name
        
        return None