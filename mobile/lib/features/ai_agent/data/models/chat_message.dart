enum ChatRole { user, assistant, system }

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
    this.contextNoteIds = const [],
  });

  final String id;
  final ChatRole role;
  final String content;
  final DateTime createdAt;
  final List<int> contextNoteIds;

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: (json['id'] ?? DateTime.now().millisecondsSinceEpoch).toString(),
        role: switch (json['role']) {
          'user' => ChatRole.user,
          'assistant' => ChatRole.assistant,
          _ => ChatRole.system,
        },
        content: (json['content'] as String?) ?? '',
        createdAt: json['created_at'] != null
            ? DateTime.parse(json['created_at'] as String)
            : DateTime.now(),
        contextNoteIds:
            ((json['context_note_ids'] as List?) ?? const []).cast<num>().map((e) => e.toInt()).toList(),
      );
}

class MemoryFact {
  const MemoryFact({
    required this.id,
    required this.text,
    required this.sourceType,
    required this.createdAt,
  });

  final int id;
  final String text;
  final String sourceType;
  final DateTime createdAt;

  factory MemoryFact.fromJson(Map<String, dynamic> json) => MemoryFact(
        id: (json['id'] as num).toInt(),
        text: (json['fact_text'] as String?) ?? (json['text'] as String? ?? ''),
        sourceType: (json['source_type'] as String?) ?? 'manual',
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
