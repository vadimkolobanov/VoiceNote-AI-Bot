import 'package:flutter/foundation.dart';

/// Fact — отражает /api/v1/facts (PRODUCT_PLAN.md §4.4 + §5.2).
@immutable
class Fact {
  const Fact({
    required this.id,
    required this.kind,
    required this.key,
    required this.value,
    required this.confidence,
    required this.sourceMomentIds,
    required this.createdAtIso,
    required this.updatedAtIso,
  });

  final int id;
  final String kind; // 'person' | 'place' | 'preference' | 'schedule' | 'other'
  final String key;
  final Map<String, dynamic> value;
  final double confidence;
  final List<int> sourceMomentIds;
  final String createdAtIso;
  final String updatedAtIso;

  factory Fact.fromJson(Map<String, dynamic> json) => Fact(
        id: (json['id'] as num).toInt(),
        kind: json['kind'] as String,
        key: json['key'] as String,
        value: (json['value'] as Map<String, dynamic>?) ?? const {},
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.5,
        sourceMomentIds: ((json['source_moment_ids'] as List<dynamic>?) ?? const [])
            .map((e) => (e as num).toInt())
            .toList(),
        createdAtIso: (json['created_at'] as String?) ?? '',
        updatedAtIso: (json['updated_at'] as String?) ?? '',
      );

  /// Краткое представление value для списка.
  String get valueBrief {
    if (value.isEmpty) return key;
    // Берём первое строковое поле, фолбэк — JSON-склейка.
    for (final entry in value.entries) {
      if (entry.value is String && (entry.value as String).isNotEmpty) {
        return '${entry.key}: ${entry.value}';
      }
    }
    return value.entries.map((e) => '${e.key}: ${e.value}').join(', ');
  }
}
