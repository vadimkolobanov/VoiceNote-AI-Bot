/// Canonical note types. Maps to `notes.type` enum on the backend.
enum NoteType {
  note,
  task,
  idea,
  shopping;

  static NoteType parse(String? raw) {
    switch (raw) {
      case 'task':
        return NoteType.task;
      case 'idea':
        return NoteType.idea;
      case 'shopping':
        return NoteType.shopping;
      default:
        return NoteType.note;
    }
  }

  String get apiValue => name;
}

class Note {
  const Note({
    required this.id,
    required this.ownerId,
    required this.type,
    required this.correctedText,
    required this.createdAt,
    required this.updatedAt,
    required this.isArchived,
    required this.isCompleted,
    this.summaryText,
    this.category,
    this.noteTakenAt,
    this.dueDate,
    this.recurrenceRule,
    this.llmAnalysisJson,
  });

  final int id;
  final int ownerId;
  final NoteType type;
  final String? summaryText;
  final String correctedText;
  final String? category;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? noteTakenAt;
  final DateTime? dueDate;
  final String? recurrenceRule;
  final bool isArchived;
  final bool isCompleted;
  final Map<String, dynamic>? llmAnalysisJson;

  bool get isShoppingList => type == NoteType.shopping;
  bool get isTask => type == NoteType.task;

  String get displayTitle {
    final s = (summaryText ?? '').trim();
    if (s.isNotEmpty) return s;
    return correctedText.trim().split('\n').first;
  }

  factory Note.fromJson(Map<String, dynamic> json) => Note(
        id: (json['note_id'] as num).toInt(),
        ownerId: (json['owner_id'] as num).toInt(),
        type: NoteType.parse(json['type'] as String?),
        summaryText: json['summary_text'] as String?,
        correctedText: (json['corrected_text'] as String?) ?? '',
        category: json['category'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
        noteTakenAt: _parseDate(json['note_taken_at']),
        dueDate: _parseDate(json['due_date']),
        recurrenceRule: json['recurrence_rule'] as String?,
        isArchived: (json['is_archived'] as bool?) ?? false,
        isCompleted: (json['is_completed'] as bool?) ?? false,
        llmAnalysisJson: json['llm_analysis_json'] as Map<String, dynamic>?,
      );

  static DateTime? _parseDate(Object? v) {
    if (v == null) return null;
    if (v is String && v.isNotEmpty) return DateTime.tryParse(v);
    return null;
  }

  Note copyWith({
    String? summaryText,
    String? correctedText,
    String? category,
    bool? isArchived,
    bool? isCompleted,
    DateTime? dueDate,
  }) {
    return Note(
      id: id,
      ownerId: ownerId,
      type: type,
      summaryText: summaryText ?? this.summaryText,
      correctedText: correctedText ?? this.correctedText,
      category: category ?? this.category,
      createdAt: createdAt,
      updatedAt: DateTime.now(),
      noteTakenAt: noteTakenAt,
      dueDate: dueDate ?? this.dueDate,
      recurrenceRule: recurrenceRule,
      isArchived: isArchived ?? this.isArchived,
      isCompleted: isCompleted ?? this.isCompleted,
      llmAnalysisJson: llmAnalysisJson,
    );
  }
}

class PaginatedNotes {
  const PaginatedNotes({
    required this.items,
    required this.total,
    required this.page,
    required this.perPage,
    required this.totalPages,
  });

  final List<Note> items;
  final int total;
  final int page;
  final int perPage;
  final int totalPages;

  bool get hasMore => page < totalPages;

  factory PaginatedNotes.fromJson(Map<String, dynamic> json) => PaginatedNotes(
        items: (json['items'] as List)
            .map((e) => Note.fromJson(e as Map<String, dynamic>))
            .toList(growable: false),
        total: (json['total'] as num).toInt(),
        page: (json['page'] as num).toInt(),
        perPage: (json['per_page'] as num).toInt(),
        totalPages: (json['total_pages'] as num).toInt(),
      );
}
