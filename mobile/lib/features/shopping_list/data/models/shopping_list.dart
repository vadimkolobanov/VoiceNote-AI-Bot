class ShoppingItem {
  const ShoppingItem({
    required this.name,
    required this.checked,
    this.addedBy,
  });

  final String name;
  final bool checked;
  final int? addedBy;

  factory ShoppingItem.fromJson(Map<String, dynamic> json) => ShoppingItem(
        name: (json['item_name'] as String?) ?? (json['name'] as String? ?? ''),
        checked: (json['checked'] as bool?) ?? false,
        addedBy: (json['added_by'] as num?)?.toInt(),
      );

  ShoppingItem copyWith({bool? checked}) => ShoppingItem(
        name: name,
        checked: checked ?? this.checked,
        addedBy: addedBy,
      );
}

class ShoppingList {
  const ShoppingList({
    required this.noteId,
    required this.items,
  });

  final int noteId;
  final List<ShoppingItem> items;

  factory ShoppingList.fromJson(Map<String, dynamic> json) {
    final analysis = json['llm_analysis_json'] as Map<String, dynamic>?;
    final rawItems = (analysis?['items'] as List?) ?? const <dynamic>[];
    return ShoppingList(
      noteId: (json['note_id'] as num?)?.toInt() ?? 0,
      items: rawItems
          .map((e) => ShoppingItem.fromJson(e as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
