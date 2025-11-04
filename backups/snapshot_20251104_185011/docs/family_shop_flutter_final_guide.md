# Family Shop Integration Guide for Flutter

## Overview

The Family Shop system allows users to purchase themes, avatars, banners, and bundles using either personal SBD tokens or family SBD tokens. Family purchases require admin approval through a purchase request system, while personal purchases are processed immediately.

## Key Features

- **Dual Payment Methods**: Personal SBD or Family SBD accounts
- **Purchase Requests**: Admin approval workflow for family purchases
- **Token Requests**: Family members can request tokens from family accounts
- **Real-time Updates**: WebSocket notifications for request status changes
- **Spending Permissions**: Configurable limits and approval thresholds
- **Transaction Safety**: MongoDB transactions ensure data consistency

## API Endpoints

### Shop Purchase Endpoints

#### POST `/shop/buy`
Purchase an item using either personal or family SBD.

**Request Body:**
```json
{
  "item_id": "string",
  "payment_method": "personal" | "family",
  "family_id": "string" // Required if payment_method is "family"
}
```

**Response (Immediate Purchase):**
```json
{
  "success": true,
  "transaction_id": "string",
  "item": {
    "id": "string",
    "name": "string",
    "type": "theme" | "avatar" | "banner" | "bundle",
    "price": 100
  }
}
```

**Response (Purchase Request Created):**
```json
{
  "success": true,
  "request_id": "string",
  "status": "pending_approval",
  "message": "Purchase request submitted for admin approval"
}
```

**Error Responses:**
- `400`: Invalid payment method or insufficient funds
- `403`: Family spending permissions denied
- `404`: Item not found
- `429`: Rate limit exceeded

### Family Purchase Request Endpoints

#### GET `/family/{family_id}/purchase-requests`
Get all purchase requests for a family.

**Query Parameters:**
- `status`: `pending` | `approved` | `denied` | `expired`
- `requester_id`: Filter by specific family member
- `limit`: Number of results (default: 50, max: 100)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
{
  "requests": [
    {
      "id": "string",
      "family_id": "string",
      "requester_id": "string",
      "item_id": "string",
      "item_name": "string",
      "item_type": "theme" | "avatar" | "banner" | "bundle",
      "price": 100,
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": "2024-01-08T00:00:00Z",
      "approved_by": null,
      "approved_at": null,
      "denied_reason": null
    }
  ],
  "total": 25,
  "has_more": true
}
```

#### POST `/family/{family_id}/purchase-requests/{request_id}/approve`
Approve a purchase request (Admin only).

**Response:**
```json
{
  "success": true,
  "transaction_id": "string",
  "message": "Purchase request approved and processed"
}
```

#### POST `/family/{family_id}/purchase-requests/{request_id}/deny`
Deny a purchase request (Admin only).

**Request Body:**
```json
{
  "reason": "string" // Optional denial reason
}
```

**Response:**
```json
{
  "success": true,
  "message": "Purchase request denied"
}
```

### Family Token Request Endpoints

#### POST `/family/{family_id}/token-requests`
Create a token request from family account.

**Request Body:**
```json
{
  "amount": 500,
  "reason": "string" // Optional
}
```

**Response (Auto-approved):**
```json
{
  "success": true,
  "transaction_id": "string",
  "message": "Token request auto-approved and processed"
}
```

**Response (Pending Approval):**
```json
{
  "success": true,
  "request_id": "string",
  "status": "pending_approval",
  "message": "Token request submitted for admin approval"
}
```

#### GET `/family/{family_id}/token-requests`
Get all token requests for a family.

**Query Parameters:**
- `status`: `pending` | `approved` | `denied` | `expired`
- `requester_id`: Filter by specific family member
- `limit`: Number of results (default: 50, max: 100)
- `offset`: Pagination offset (default: 0)

#### POST `/family/{family_id}/token-requests/{request_id}/approve`
Approve a token request (Admin only).

#### POST `/family/{family_id}/token-requests/{request_id}/deny`
Deny a token request (Admin only).

### Family Wallet Endpoints

#### GET `/family/{family_id}/wallet`
Get family wallet information.

**Response:**
```json
{
  "family_id": "string",
  "balance": 5000,
  "spending_permissions": {
    "require_approval": true,
    "approval_threshold": 200,
    "max_daily_spend": 1000,
    "allowed_item_types": ["theme", "avatar", "banner"]
  },
  "token_request_settings": {
    "auto_approve_threshold": 100,
    "require_approval_above": 500
  }
}
```

## Flutter Implementation

### Models

```dart
// Shop Item Model
class ShopItem {
  final String id;
  final String name;
  final String type; // 'theme', 'avatar', 'banner', 'bundle'
  final int price;
  final String? description;
  final String? imageUrl;

  ShopItem({
    required this.id,
    required this.name,
    required this.type,
    required this.price,
    this.description,
    this.imageUrl,
  });

  factory ShopItem.fromJson(Map<String, dynamic> json) {
    return ShopItem(
      id: json['id'],
      name: json['name'],
      type: json['type'],
      price: json['price'],
      description: json['description'],
      imageUrl: json['image_url'],
    );
  }
}

// Purchase Request Model
class PurchaseRequest {
  final String id;
  final String familyId;
  final String requesterId;
  final String itemId;
  final String itemName;
  final String itemType;
  final int price;
  final String status; // 'pending', 'approved', 'denied', 'expired'
  final DateTime createdAt;
  final DateTime expiresAt;
  final String? approvedBy;
  final DateTime? approvedAt;
  final String? deniedReason;

  PurchaseRequest({
    required this.id,
    required this.familyId,
    required this.requesterId,
    required this.itemId,
    required this.itemName,
    required this.itemType,
    required this.price,
    required this.status,
    required this.createdAt,
    required this.expiresAt,
    this.approvedBy,
    this.approvedAt,
    this.deniedReason,
  });

  factory PurchaseRequest.fromJson(Map<String, dynamic> json) {
    return PurchaseRequest(
      id: json['id'],
      familyId: json['family_id'],
      requesterId: json['requester_id'],
      itemId: json['item_id'],
      itemName: json['item_name'],
      itemType: json['item_type'],
      price: json['price'],
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
      expiresAt: DateTime.parse(json['expires_at']),
      approvedBy: json['approved_by'],
      approvedAt: json['approved_at'] != null ? DateTime.parse(json['approved_at']) : null,
      deniedReason: json['denied_reason'],
    );
  }
}

// Token Request Model
class TokenRequest {
  final String id;
  final String familyId;
  final String requesterId;
  final int amount;
  final String? reason;
  final String status; // 'pending', 'approved', 'denied', 'expired'
  final DateTime createdAt;
  final DateTime expiresAt;
  final String? approvedBy;
  final DateTime? approvedAt;
  final String? deniedReason;

  TokenRequest({
    required this.id,
    required this.familyId,
    required this.requesterId,
    required this.amount,
    this.reason,
    required this.status,
    required this.createdAt,
    required this.expiresAt,
    this.approvedBy,
    this.approvedAt,
    this.deniedReason,
  });

  factory TokenRequest.fromJson(Map<String, dynamic> json) {
    return TokenRequest(
      id: json['id'],
      familyId: json['family_id'],
      requesterId: json['requester_id'],
      amount: json['amount'],
      reason: json['reason'],
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
      expiresAt: DateTime.parse(json['expires_at']),
      approvedBy: json['approved_by'],
      approvedAt: json['approved_at'] != null ? DateTime.parse(json['approved_at']) : null,
      deniedReason: json['denied_reason'],
    );
  }
}

// Family Wallet Model
class FamilyWallet {
  final String familyId;
  final int balance;
  final SpendingPermissions spendingPermissions;
  final TokenRequestSettings tokenRequestSettings;

  FamilyWallet({
    required this.familyId,
    required this.balance,
    required this.spendingPermissions,
    required this.tokenRequestSettings,
  });

  factory FamilyWallet.fromJson(Map<String, dynamic> json) {
    return FamilyWallet(
      familyId: json['family_id'],
      balance: json['balance'],
      spendingPermissions: SpendingPermissions.fromJson(json['spending_permissions']),
      tokenRequestSettings: TokenRequestSettings.fromJson(json['token_request_settings']),
    );
  }
}

class SpendingPermissions {
  final bool requireApproval;
  final int approvalThreshold;
  final int maxDailySpend;
  final List<String> allowedItemTypes;

  SpendingPermissions({
    required this.requireApproval,
    required this.approvalThreshold,
    required this.maxDailySpend,
    required this.allowedItemTypes,
  });

  factory SpendingPermissions.fromJson(Map<String, dynamic> json) {
    return SpendingPermissions(
      requireApproval: json['require_approval'],
      approvalThreshold: json['approval_threshold'],
      maxDailySpend: json['max_daily_spend'],
      allowedItemTypes: List<String>.from(json['allowed_item_types']),
    );
  }
}

class TokenRequestSettings {
  final int autoApproveThreshold;
  final int requireApprovalAbove;

  TokenRequestSettings({
    required this.autoApproveThreshold,
    required this.requireApprovalAbove,
  });

  factory TokenRequestSettings.fromJson(Map<String, dynamic> json) {
    return TokenRequestSettings(
      autoApproveThreshold: json['auto_approve_threshold'],
      requireApprovalAbove: json['require_approval_above'],
    );
  }
}
```

### API Service

```dart
import 'package:dio/dio.dart';
import 'package:riverpod/riverpod.dart';

class FamilyShopApiService {
  final Dio _dio;
  final String baseUrl;

  FamilyShopApiService(this._dio, this.baseUrl);

  // Shop Purchase
  Future<Either<ApiError, PurchaseResponse>> purchaseItem({
    required String itemId,
    required String paymentMethod,
    String? familyId,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/shop/buy',
        data: {
          'item_id': itemId,
          'payment_method': paymentMethod,
          if (familyId != null) 'family_id': familyId,
        },
      );

      if (response.data['success'] == true) {
        if (response.data.containsKey('transaction_id')) {
          // Immediate purchase
          return Right(PurchaseResponse.immediate(
            transactionId: response.data['transaction_id'],
            item: ShopItem.fromJson(response.data['item']),
          ));
        } else {
          // Purchase request created
          return Right(PurchaseResponse.request(
            requestId: response.data['request_id'],
            status: response.data['status'],
            message: response.data['message'],
          ));
        }
      } else {
        return Left(ApiError.fromJson(response.data));
      }
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Get Purchase Requests
  Future<Either<ApiError, PurchaseRequestsResponse>> getPurchaseRequests({
    required String familyId,
    String? status,
    String? requesterId,
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final response = await _dio.get(
        '$baseUrl/family/$familyId/purchase-requests',
        queryParameters: {
          if (status != null) 'status': status,
          if (requesterId != null) 'requester_id': requesterId,
          'limit': limit,
          'offset': offset,
        },
      );

      return Right(PurchaseRequestsResponse.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Approve Purchase Request
  Future<Either<ApiError, SuccessResponse>> approvePurchaseRequest({
    required String familyId,
    required String requestId,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/family/$familyId/purchase-requests/$requestId/approve',
      );

      return Right(SuccessResponse.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Deny Purchase Request
  Future<Either<ApiError, SuccessResponse>> denyPurchaseRequest({
    required String familyId,
    required String requestId,
    String? reason,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/family/$familyId/purchase-requests/$requestId/deny',
        data: {
          if (reason != null) 'reason': reason,
        },
      );

      return Right(SuccessResponse.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Create Token Request
  Future<Either<ApiError, TokenRequestResponse>> createTokenRequest({
    required String familyId,
    required int amount,
    String? reason,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/family/$familyId/token-requests',
        data: {
          'amount': amount,
          if (reason != null) 'reason': reason,
        },
      );

      if (response.data['success'] == true) {
        if (response.data.containsKey('transaction_id')) {
          // Auto-approved
          return Right(TokenRequestResponse.immediate(
            transactionId: response.data['transaction_id'],
            message: response.data['message'],
          ));
        } else {
          // Pending approval
          return Right(TokenRequestResponse.request(
            requestId: response.data['request_id'],
            status: response.data['status'],
            message: response.data['message'],
          ));
        }
      } else {
        return Left(ApiError.fromJson(response.data));
      }
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Get Token Requests
  Future<Either<ApiError, TokenRequestsResponse>> getTokenRequests({
    required String familyId,
    String? status,
    String? requesterId,
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final response = await _dio.get(
        '$baseUrl/family/$familyId/token-requests',
        queryParameters: {
          if (status != null) 'status': status,
          if (requesterId != null) 'requester_id': requesterId,
          'limit': limit,
          'offset': offset,
        },
      );

      return Right(TokenRequestsResponse.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Approve Token Request
  Future<Either<ApiError, SuccessResponse>> approveTokenRequest({
    required String familyId,
    required String requestId,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/family/$familyId/token-requests/$requestId/approve',
      );

      return Right(SuccessResponse.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Deny Token Request
  Future<Either<ApiError, SuccessResponse>> denyTokenRequest({
    required String familyId,
    required String requestId,
    String? reason,
  }) async {
    try {
      final response = await _dio.post(
        '$baseUrl/family/$familyId/token-requests/$requestId/deny',
        data: {
          if (reason != null) 'reason': reason,
        },
      );

      return Right(SuccessResponse.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }

  // Get Family Wallet
  Future<Either<ApiError, FamilyWallet>> getFamilyWallet(String familyId) async {
    try {
      final response = await _dio.get('$baseUrl/family/$familyId/wallet');
      return Right(FamilyWallet.fromJson(response.data));
    } on DioException catch (e) {
      return Left(ApiError.fromDioException(e));
    }
  }
}

// Response Models
class PurchaseResponse {
  final String type; // 'immediate' or 'request'
  final String? transactionId;
  final ShopItem? item;
  final String? requestId;
  final String? status;
  final String? message;

  PurchaseResponse.immediate({
    required this.transactionId,
    required this.item,
  }) : type = 'immediate', requestId = null, status = null, message = null;

  PurchaseResponse.request({
    required this.requestId,
    required this.status,
    required this.message,
  }) : type = 'request', transactionId = null, item = null;
}

class PurchaseRequestsResponse {
  final List<PurchaseRequest> requests;
  final int total;
  final bool hasMore;

  PurchaseRequestsResponse({
    required this.requests,
    required this.total,
    required this.hasMore,
  });

  factory PurchaseRequestsResponse.fromJson(Map<String, dynamic> json) {
    return PurchaseRequestsResponse(
      requests: (json['requests'] as List)
          .map((r) => PurchaseRequest.fromJson(r))
          .toList(),
      total: json['total'],
      hasMore: json['has_more'],
    );
  }
}

class TokenRequestResponse {
  final String type; // 'immediate' or 'request'
  final String? transactionId;
  final String? requestId;
  final String? status;
  final String? message;

  TokenRequestResponse.immediate({
    required this.transactionId,
    required this.message,
  }) : type = 'immediate', requestId = null, status = null;

  TokenRequestResponse.request({
    required this.requestId,
    required this.status,
    required this.message,
  }) : type = 'request', transactionId = null;
}

class TokenRequestsResponse {
  final List<TokenRequest> requests;
  final int total;
  final bool hasMore;

  TokenRequestsResponse({
    required this.requests,
    required this.total,
    required this.hasMore,
  });

  factory TokenRequestsResponse.fromJson(Map<String, dynamic> json) {
    return TokenRequestsResponse(
      requests: (json['requests'] as List)
          .map((r) => TokenRequest.fromJson(r))
          .toList(),
      total: json['total'],
      hasMore: json['has_more'],
    );
  }
}

class SuccessResponse {
  final bool success;
  final String message;
  final String? transactionId;

  SuccessResponse({
    required this.success,
    required this.message,
    this.transactionId,
  });

  factory SuccessResponse.fromJson(Map<String, dynamic> json) {
    return SuccessResponse(
      success: json['success'],
      message: json['message'],
      transactionId: json['transaction_id'],
    );
  }
}

class ApiError {
  final String message;
  final int? statusCode;
  final String? errorCode;

  ApiError({
    required this.message,
    this.statusCode,
    this.errorCode,
  });

  factory ApiError.fromJson(Map<String, dynamic> json) {
    return ApiError(
      message: json['message'] ?? 'Unknown error',
      statusCode: json['status_code'],
      errorCode: json['error_code'],
    );
  }

  factory ApiError.fromDioException(DioException e) {
    return ApiError(
      message: e.response?.data?['message'] ?? e.message ?? 'Network error',
      statusCode: e.response?.statusCode,
      errorCode: e.response?.data?['error_code'],
    );
  }
}
```

### Riverpod State Management

```dart
import 'package:riverpod/riverpod.dart';

// API Service Provider
final apiServiceProvider = Provider<FamilyShopApiService>((ref) {
  final dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 10),
  ));

  // Add auth interceptor
  dio.interceptors.add(AuthInterceptor());

  return FamilyShopApiService(dio, 'https://api.yourapp.com');
});

// Family Wallet Provider
final familyWalletProvider = StateNotifierProvider.family<
    FamilyWalletNotifier,
    AsyncValue<FamilyWallet>,
    String>((ref, familyId) {
  final apiService = ref.watch(apiServiceProvider);
  return FamilyWalletNotifier(apiService, familyId);
});

class FamilyWalletNotifier extends StateNotifier<AsyncValue<FamilyWallet>> {
  final FamilyShopApiService _apiService;
  final String _familyId;

  FamilyWalletNotifier(this._apiService, this._familyId)
      : super(const AsyncValue.loading()) {
    loadWallet();
  }

  Future<void> loadWallet() async {
    state = const AsyncValue.loading();
    final result = await _apiService.getFamilyWallet(_familyId);

    result.fold(
      (error) => state = AsyncValue.error(error, StackTrace.current),
      (wallet) => state = AsyncValue.data(wallet),
    );
  }

  Future<void> refresh() => loadWallet();
}

// Purchase Requests Provider
final purchaseRequestsProvider = StateNotifierProvider.family<
    PurchaseRequestsNotifier,
    AsyncValue<List<PurchaseRequest>>,
    String>((ref, familyId) {
  final apiService = ref.watch(apiServiceProvider);
  return PurchaseRequestsNotifier(apiService, familyId);
});

class PurchaseRequestsNotifier
    extends StateNotifier<AsyncValue<List<PurchaseRequest>>> {
  final FamilyShopApiService _apiService;
  final String _familyId;

  PurchaseRequestsNotifier(this._apiService, this._familyId)
      : super(const AsyncValue.loading()) {
    loadRequests();
  }

  Future<void> loadRequests({
    String? status,
    String? requesterId,
  }) async {
    state = const AsyncValue.loading();
    final result = await _apiService.getPurchaseRequests(
      familyId: _familyId,
      status: status,
      requesterId: requesterId,
    );

    result.fold(
      (error) => state = AsyncValue.error(error, StackTrace.current),
      (response) => state = AsyncValue.data(response.requests),
    );
  }

  Future<bool> approveRequest(String requestId) async {
    final result = await _apiService.approvePurchaseRequest(
      familyId: _familyId,
      requestId: requestId,
    );

    return result.fold(
      (error) => false,
      (response) => response.success,
    );
  }

  Future<bool> denyRequest(String requestId, {String? reason}) async {
    final result = await _apiService.denyPurchaseRequest(
      familyId: _familyId,
      requestId: requestId,
      reason: reason,
    );

    return result.fold(
      (error) => false,
      (response) => response.success,
    );
  }

  Future<void> refresh() => loadRequests();
}

// Token Requests Provider
final tokenRequestsProvider = StateNotifierProvider.family<
    TokenRequestsNotifier,
    AsyncValue<List<TokenRequest>>,
    String>((ref, familyId) {
  final apiService = ref.watch(apiServiceProvider);
  return TokenRequestsNotifier(apiService, familyId);
});

class TokenRequestsNotifier
    extends StateNotifier<AsyncValue<List<TokenRequest>>> {
  final FamilyShopApiService _apiService;
  final String _familyId;

  TokenRequestsNotifier(this._apiService, this._familyId)
      : super(const AsyncValue.loading()) {
    loadRequests();
  }

  Future<void> loadRequests({
    String? status,
    String? requesterId,
  }) async {
    state = const AsyncValue.loading();
    final result = await _apiService.getTokenRequests(
      familyId: _familyId,
      status: status,
      requesterId: requesterId,
    );

    result.fold(
      (error) => state = AsyncValue.error(error, StackTrace.current),
      (response) => state = AsyncValue.data(response.requests),
    );
  }

  Future<TokenRequestResponse?> createRequest({
    required int amount,
    String? reason,
  }) async {
    final result = await _apiService.createTokenRequest(
      familyId: _familyId,
      amount: amount,
      reason: reason,
    );

    return result.fold(
      (error) => null,
      (response) => response,
    );
  }

  Future<bool> approveRequest(String requestId) async {
    final result = await _apiService.approveTokenRequest(
      familyId: _familyId,
      requestId: requestId,
    );

    return result.fold(
      (error) => false,
      (response) => response.success,
    );
  }

  Future<bool> denyRequest(String requestId, {String? reason}) async {
    final result = await _apiService.denyTokenRequest(
      familyId: _familyId,
      requestId: requestId,
      reason: reason,
    );

    return result.fold(
      (error) => false,
      (response) => response.success,
    );
  }

  Future<void> refresh() => loadRequests();
}

// Shop Purchase Provider
final shopPurchaseProvider = StateNotifierProvider<ShopPurchaseNotifier, AsyncValue<void>>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return ShopPurchaseNotifier(apiService);
});

class ShopPurchaseNotifier extends StateNotifier<AsyncValue<void>> {
  final FamilyShopApiService _apiService;

  ShopPurchaseNotifier(this._apiService) : super(const AsyncValue.data(null));

  Future<PurchaseResponse?> purchaseItem({
    required String itemId,
    required String paymentMethod,
    String? familyId,
  }) async {
    state = const AsyncValue.loading();

    final result = await _apiService.purchaseItem(
      itemId: itemId,
      paymentMethod: paymentMethod,
      familyId: familyId,
    );

    return result.fold(
      (error) {
        state = AsyncValue.error(error, StackTrace.current);
        return null;
      },
      (response) {
        state = const AsyncValue.data(null);
        return response;
      },
    );
  }
}
```

### UI Implementation Examples

#### Shop Item Purchase Widget

```dart
class ShopItemCard extends ConsumerWidget {
  final ShopItem item;
  final String? familyId;

  const ShopItemCard({
    super.key,
    required this.item,
    this.familyId,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final purchaseState = ref.watch(shopPurchaseProvider);
    final walletAsync = familyId != null
        ? ref.watch(familyWalletProvider(familyId!))
        : null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (item.imageUrl != null)
              Image.network(item.imageUrl!, height: 100, width: double.infinity, fit: BoxFit.cover),
            const SizedBox(height: 8),
            Text(item.name, style: Theme.of(context).textTheme.titleMedium),
            Text('${item.price} SBD', style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: purchaseState.isLoading
                        ? null
                        : () => _purchase(context, ref, 'personal'),
                    child: purchaseState.isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Buy with Personal'),
                  ),
                ),
                if (familyId != null && walletAsync?.value?.balance != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: purchaseState.isLoading ||
                              (walletAsync!.value!.balance < item.price)
                          ? null
                          : () => _purchase(context, ref, 'family'),
                      child: const Text('Buy with Family'),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _purchase(BuildContext context, WidgetRef ref, String paymentMethod) async {
    final result = await ref.read(shopPurchaseProvider.notifier).purchaseItem(
      itemId: item.id,
      paymentMethod: paymentMethod,
      familyId: familyId,
    );

    if (result != null) {
      if (result.type == 'immediate') {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Purchase successful! Transaction: ${result.transactionId}')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Purchase request submitted for approval')),
        );
      }
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Purchase failed. Please try again.')),
      );
    }
  }
}
```

#### Purchase Requests Management Widget

```dart
class PurchaseRequestsScreen extends ConsumerWidget {
  final String familyId;

  const PurchaseRequestsScreen({super.key, required this.familyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final requestsAsync = ref.watch(purchaseRequestsProvider(familyId));

    return Scaffold(
      appBar: AppBar(title: const Text('Purchase Requests')),
      body: requestsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(child: Text('Error: $error')),
        data: (requests) => ListView.builder(
          itemCount: requests.length,
          itemBuilder: (context, index) {
            final request = requests[index];
            return PurchaseRequestCard(
              request: request,
              familyId: familyId,
              onApprove: () => _approveRequest(context, ref, request.id),
              onDeny: () => _denyRequest(context, ref, request.id),
            );
          },
        ),
      ),
    );
  }

  Future<void> _approveRequest(BuildContext context, WidgetRef ref, String requestId) async {
    final success = await ref.read(purchaseRequestsProvider(familyId).notifier).approveRequest(requestId);
    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Request approved')),
      );
      ref.invalidate(purchaseRequestsProvider(familyId));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to approve request')),
      );
    }
  }

  Future<void> _denyRequest(BuildContext context, WidgetRef ref, String requestId) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => DenyReasonDialog(),
    );

    if (reason != null) {
      final success = await ref.read(purchaseRequestsProvider(familyId).notifier).denyRequest(
        requestId,
        reason: reason,
      );
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Request denied')),
        );
        ref.invalidate(purchaseRequestsProvider(familyId));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to deny request')),
        );
      }
    }
  }
}

class PurchaseRequestCard extends StatelessWidget {
  final PurchaseRequest request;
  final String familyId;
  final VoidCallback onApprove;
  final VoidCallback onDeny;

  const PurchaseRequestCard({
    super.key,
    required this.request,
    required this.familyId,
    required this.onApprove,
    required this.onDeny,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(request.itemName, style: Theme.of(context).textTheme.titleMedium),
            Text('${request.price} SBD', style: Theme.of(context).textTheme.bodyLarge),
            Text('Requested by: ${request.requesterId}'),
            Text('Status: ${request.status}'),
            if (request.status == 'pending') ...[
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: onApprove,
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                      child: const Text('Approve'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: onDeny,
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
                      child: const Text('Deny'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

#### Token Request Widget

```dart
class TokenRequestScreen extends ConsumerWidget {
  final String familyId;

  const TokenRequestScreen({super.key, required this.familyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final requestsAsync = ref.watch(tokenRequestsProvider(familyId));

    return Scaffold(
      appBar: AppBar(title: const Text('Token Requests')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: ElevatedButton(
              onPressed: () => _showRequestDialog(context, ref),
              child: const Text('Request Tokens'),
            ),
          ),
          Expanded(
            child: requestsAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, stack) => Center(child: Text('Error: $error')),
              data: (requests) => ListView.builder(
                itemCount: requests.length,
                itemBuilder: (context, index) {
                  final request = requests[index];
                  return TokenRequestCard(
                    request: request,
                    familyId: familyId,
                    onApprove: () => _approveRequest(context, ref, request.id),
                    onDeny: () => _denyRequest(context, ref, request.id),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _showRequestDialog(BuildContext context, WidgetRef ref) async {
    final result = await showDialog<TokenRequestResult>(
      context: context,
      builder: (context) => const TokenRequestDialog(),
    );

    if (result != null) {
      final response = await ref.read(tokenRequestsProvider(familyId).notifier).createRequest(
        amount: result.amount,
        reason: result.reason,
      );

      if (response != null) {
        if (response.type == 'immediate') {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Tokens transferred! Transaction: ${response.transactionId}')),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Token request submitted for approval')),
          );
        }
        ref.invalidate(tokenRequestsProvider(familyId));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to create token request')),
        );
      }
    }
  }

  Future<void> _approveRequest(BuildContext context, WidgetRef ref, String requestId) async {
    final success = await ref.read(tokenRequestsProvider(familyId).notifier).approveRequest(requestId);
    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Token request approved')),
      );
      ref.invalidate(tokenRequestsProvider(familyId));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to approve request')),
      );
    }
  }

  Future<void> _denyRequest(BuildContext context, WidgetRef ref, String requestId) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => DenyReasonDialog(),
    );

    if (reason != null) {
      final success = await ref.read(tokenRequestsProvider(familyId).notifier).denyRequest(
        requestId,
        reason: reason,
      );
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Token request denied')),
        );
        ref.invalidate(tokenRequestsProvider(familyId));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to deny request')),
        );
      }
    }
  }
}

class TokenRequestDialog extends StatefulWidget {
  const TokenRequestDialog({super.key});

  @override
  State<TokenRequestDialog> createState() => _TokenRequestDialogState();
}

class _TokenRequestDialogState extends State<TokenRequestDialog> {
  final _amountController = TextEditingController();
  final _reasonController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Request Tokens'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _amountController,
            decoration: const InputDecoration(labelText: 'Amount'),
            keyboardType: TextInputType.number,
          ),
          TextField(
            controller: _reasonController,
            decoration: const InputDecoration(labelText: 'Reason (optional)'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () {
            final amount = int.tryParse(_amountController.text);
            if (amount != null && amount > 0) {
              Navigator.of(context).pop(TokenRequestResult(
                amount: amount,
                reason: _reasonController.text.isEmpty ? null : _reasonController.text,
              ));
            }
          },
          child: const Text('Request'),
        ),
      ],
    );
  }
}

class TokenRequestResult {
  final int amount;
  final String? reason;

  TokenRequestResult({required this.amount, this.reason});
}
```

### WebSocket Integration

```dart
import 'package:web_socket_channel/web_socket_channel.dart';

class FamilyWebSocketService {
  WebSocketChannel? _channel;
  final StreamController<Map<String, dynamic>> _eventController = StreamController.broadcast();

  Stream<Map<String, dynamic>> get events => _eventController.stream;

  void connect(String familyId, String token) {
    _channel = WebSocketChannel.connect(
      Uri.parse('wss://api.yourapp.com/ws/family/$familyId?token=$token'),
    );

    _channel!.stream.listen(
      (message) {
        final data = jsonDecode(message);
        _eventController.add(data);
      },
      onError: (error) {
        print('WebSocket error: $error');
      },
      onDone: () {
        print('WebSocket connection closed');
      },
    );
  }

  void disconnect() {
    _channel?.sink.close();
    _channel = null;
  }
}

// Usage in Riverpod
final webSocketProvider = Provider<FamilyWebSocketService>((ref) {
  return FamilyWebSocketService();
});

final familyEventsProvider = StreamProvider.family<Map<String, dynamic>, String>((ref, familyId) {
  final wsService = ref.watch(webSocketProvider);
  final authToken = ref.watch(authTokenProvider); // Your auth token provider

  wsService.connect(familyId, authToken);

  ref.onDispose(() {
    wsService.disconnect();
  });

  return wsService.events;
});

// Listen to events in UI
class FamilyDashboard extends ConsumerWidget {
  final String familyId;

  const FamilyDashboard({super.key, required this.familyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventsAsync = ref.watch(familyEventsProvider(familyId));

    ref.listen(familyEventsProvider(familyId), (previous, next) {
      next.whenData((event) {
        switch (event['type']) {
          case 'purchase_request_created':
            // Refresh purchase requests
            ref.invalidate(purchaseRequestsProvider(familyId));
            // Show notification
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('New purchase request: ${event['item_name']}')),
            );
            break;
          case 'purchase_request_approved':
            // Refresh wallet balance
            ref.invalidate(familyWalletProvider(familyId));
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Purchase request approved')),
            );
            break;
          case 'token_request_created':
            ref.invalidate(tokenRequestsProvider(familyId));
            break;
          // Handle other events...
        }
      });
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Family Dashboard')),
      body: const Center(child: Text('Family content here')),
    );
  }
}
```

## Error Handling

### Common Error Codes

- `INSUFFICIENT_FUNDS`: Not enough tokens in personal or family account
- `FAMILY_PERMISSION_DENIED`: User doesn't have permission to spend from family account
- `APPROVAL_REQUIRED`: Purchase requires admin approval
- `REQUEST_EXPIRED`: Purchase or token request has expired
- `RATE_LIMIT_EXCEEDED`: Too many requests in short time period
- `INVALID_PAYMENT_METHOD`: Payment method not supported
- `ITEM_NOT_FOUND`: Shop item doesn't exist

### Error Handling Strategy

```dart
class ApiErrorHandler {
  static String getErrorMessage(ApiError error) {
    switch (error.errorCode) {
      case 'INSUFFICIENT_FUNDS':
        return 'Not enough tokens available';
      case 'FAMILY_PERMISSION_DENIED':
        return 'You don\'t have permission to spend from this family account';
      case 'APPROVAL_REQUIRED':
        return 'This purchase requires admin approval';
      case 'REQUEST_EXPIRED':
        return 'This request has expired';
      case 'RATE_LIMIT_EXCEEDED':
        return 'Too many requests. Please wait and try again';
      case 'INVALID_PAYMENT_METHOD':
        return 'Invalid payment method selected';
      case 'ITEM_NOT_FOUND':
        return 'Item not found in shop';
      default:
        return error.message;
    }
  }

  static void showErrorSnackBar(BuildContext context, ApiError error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(getErrorMessage(error)),
        backgroundColor: Colors.red,
      ),
    );
  }
}
```

## Testing

### Unit Tests

```dart
void main() {
  group('FamilyShopApiService', () {
    late Dio mockDio;
    late FamilyShopApiService apiService;

    setUp(() {
      mockDio = MockDio();
      apiService = FamilyShopApiService(mockDio, 'https://api.test.com');
    });

    test('purchaseItem with personal payment succeeds', () async {
      when(() => mockDio.post(any(), data: any(named: 'data')))
          .thenAnswer((_) async => Response(
                data: {
                  'success': true,
                  'transaction_id': 'tx_123',
                  'item': {'id': 'item_1', 'name': 'Test Item', 'type': 'theme', 'price': 100}
                },
                statusCode: 200,
                requestOptions: RequestOptions(path: ''),
              ));

      final result = await apiService.purchaseItem(
        itemId: 'item_1',
        paymentMethod: 'personal',
      );

      expect(result.isRight(), true);
      result.fold(
        (error) => fail('Expected success'),
        (response) {
          expect(response.type, 'immediate');
          expect(response.transactionId, 'tx_123');
          expect(response.item?.name, 'Test Item');
        },
      );
    });

    test('purchaseItem with family payment creates request', () async {
      when(() => mockDio.post(any(), data: any(named: 'data')))
          .thenAnswer((_) async => Response(
                data: {
                  'success': true,
                  'request_id': 'req_123',
                  'status': 'pending_approval',
                  'message': 'Purchase request submitted'
                },
                statusCode: 200,
                requestOptions: RequestOptions(path: ''),
              ));

      final result = await apiService.purchaseItem(
        itemId: 'item_1',
        paymentMethod: 'family',
        familyId: 'family_123',
      );

      expect(result.isRight(), true);
      result.fold(
        (error) => fail('Expected success'),
        (response) {
          expect(response.type, 'request');
          expect(response.requestId, 'req_123');
          expect(response.status, 'pending_approval');
        },
      );
    });
  });
}
```

## Security Considerations

1. **Authentication**: All API calls require valid JWT tokens
2. **Authorization**: Family membership and admin permissions are validated server-side
3. **Rate Limiting**: Prevents abuse of purchase and request endpoints
4. **Input Validation**: All monetary values and IDs are validated
5. **Transaction Safety**: MongoDB transactions ensure data consistency
6. **Audit Logging**: All financial operations are logged for compliance

## Performance Optimization

1. **Pagination**: Use limit/offset for large request lists
2. **Caching**: Cache family wallet data and shop items
3. **WebSocket**: Real-time updates reduce polling frequency
4. **Background Processing**: Heavy operations use background tasks
5. **Database Indexing**: Optimized queries for request filtering

This comprehensive guide covers all aspects of the Family Shop integration for Flutter applications, including API usage, state management, UI components, error handling, and testing strategies.</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/docs/family_shop_flutter_final_guide.md