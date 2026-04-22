/// Shopping list domain models (Phase 1 rewrite — no longer a Note).
class ShoppingListSummary {
  const ShoppingListSummary({
    required this.id,
    required this.ownerId,
    required this.title,
    required this.createdAt,
    required this.itemsCount,
    required this.checkedCount,
    this.archivedAt,
  });

  final int id;
  final int ownerId;
  final String title;
  final DateTime createdAt;
  final DateTime? archivedAt;
  final int itemsCount;
  final int checkedCount;

  bool get isArchived => archivedAt != null;
  bool get isCompleted => itemsCount > 0 && checkedCount == itemsCount;

  double get progress =>
      itemsCount == 0 ? 0 : checkedCount / itemsCount;

  factory ShoppingListSummary.fromJson(Map<String, dynamic> json) => ShoppingListSummary(
        id: (json['id'] as num).toInt(),
        ownerId: (json['owner_id'] as num).toInt(),
        title: (json['title'] as String?) ?? 'Список покупок',
        createdAt: DateTime.parse(json['created_at'] as String),
        archivedAt: json['archived_at'] != null
            ? DateTime.parse(json['archived_at'] as String)
            : null,
        itemsCount: (json['items_count'] as num?)?.toInt() ?? 0,
        checkedCount: (json['checked_count'] as num?)?.toInt() ?? 0,
      );
}

class ShoppingItem {
  const ShoppingItem({
    required this.id,
    required this.name,
    required this.position,
    required this.addedBy,
    required this.createdAt,
    this.quantity,
    this.checkedAt,
    this.checkedBy,
  });

  final int id;
  final String name;
  final String? quantity;
  final int position;
  final DateTime? checkedAt;
  final int? checkedBy;
  final int addedBy;
  final DateTime createdAt;

  bool get checked => checkedAt != null;

  ShoppingItem copyWith({
    DateTime? checkedAt,
    int? checkedBy,
    Object? clearChecked,
  }) =>
      ShoppingItem(
        id: id,
        name: name,
        quantity: quantity,
        position: position,
        addedBy: addedBy,
        createdAt: createdAt,
        checkedAt: clearChecked == true ? null : (checkedAt ?? this.checkedAt),
        checkedBy: clearChecked == true ? null : (checkedBy ?? this.checkedBy),
      );

  factory ShoppingItem.fromJson(Map<String, dynamic> json) => ShoppingItem(
        id: (json['id'] as num).toInt(),
        name: (json['name'] as String?) ?? '',
        quantity: json['quantity'] as String?,
        position: (json['position'] as num?)?.toInt() ?? 0,
        checkedAt: json['checked_at'] != null
            ? DateTime.parse(json['checked_at'] as String)
            : null,
        checkedBy: (json['checked_by'] as num?)?.toInt(),
        addedBy: (json['added_by'] as num).toInt(),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class ShoppingMember {
  const ShoppingMember({
    required this.userId,
    required this.role,
    required this.joinedAt,
    this.firstName,
    this.username,
  });

  final int userId;
  final String role; // 'owner' | 'member'
  final DateTime joinedAt;
  final String? firstName;
  final String? username;

  bool get isOwner => role == 'owner';

  String get displayName {
    final n = (firstName ?? '').trim();
    if (n.isNotEmpty) return n;
    final u = (username ?? '').trim();
    if (u.isNotEmpty) return '@$u';
    return 'id $userId';
  }

  factory ShoppingMember.fromJson(Map<String, dynamic> json) => ShoppingMember(
        userId: (json['user_id'] as num).toInt(),
        role: (json['role'] as String?) ?? 'member',
        joinedAt: DateTime.parse(json['joined_at'] as String),
        firstName: json['first_name'] as String?,
        username: json['username'] as String?,
      );
}

class ShoppingListDetail {
  const ShoppingListDetail({
    required this.id,
    required this.ownerId,
    required this.title,
    required this.createdAt,
    required this.items,
    required this.members,
    this.archivedAt,
  });

  final int id;
  final int ownerId;
  final String title;
  final DateTime createdAt;
  final DateTime? archivedAt;
  final List<ShoppingItem> items;
  final List<ShoppingMember> members;

  bool get isArchived => archivedAt != null;
  int get checkedCount => items.where((i) => i.checked).length;

  bool userIsOwner(int userId) => ownerId == userId;

  factory ShoppingListDetail.fromJson(Map<String, dynamic> json) => ShoppingListDetail(
        id: (json['id'] as num).toInt(),
        ownerId: (json['owner_id'] as num).toInt(),
        title: (json['title'] as String?) ?? 'Список покупок',
        createdAt: DateTime.parse(json['created_at'] as String),
        archivedAt: json['archived_at'] != null
            ? DateTime.parse(json['archived_at'] as String)
            : null,
        items: ((json['items'] as List?) ?? const [])
            .map((e) => ShoppingItem.fromJson(e as Map<String, dynamic>))
            .toList(growable: false),
        members: ((json['members'] as List?) ?? const [])
            .map((e) => ShoppingMember.fromJson(e as Map<String, dynamic>))
            .toList(growable: false),
      );
}

class ShoppingInvite {
  const ShoppingInvite({required this.code, required this.expiresAt});

  final String code;
  final DateTime expiresAt;

  factory ShoppingInvite.fromJson(Map<String, dynamic> json) => ShoppingInvite(
        code: json['code'] as String,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );
}
