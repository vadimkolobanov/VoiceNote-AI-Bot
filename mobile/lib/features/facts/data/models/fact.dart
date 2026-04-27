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

  /// Человеко-читаемый заголовок: основное «название» факта на русском.
  /// Скрывает технический slug-key, показывая то, что внутри value.
  String get humanLabel {
    String s(String k) => (value[k]?.toString() ?? '').trim();
    switch (kind) {
      case 'person':
        final name = s('name');
        if (name.isNotEmpty) return name;
        return _kindFallback();
      case 'place':
        final label = s('label');
        if (label.isNotEmpty) return label;
        return _kindFallback();
      case 'preference':
        final sm = s('summary');
        if (sm.isNotEmpty) return sm;
        return _kindFallback();
      case 'schedule':
        final what = s('what');
        if (what.isNotEmpty) return what;
        return _kindFallback();
      default:
        for (final v in value.values) {
          if (v is String && v.isNotEmpty) return v;
        }
        return _kindFallback();
    }
  }

  String _kindFallback() {
    switch (kind) {
      case 'person':
        return 'Человек';
      case 'place':
        return 'Место';
      case 'preference':
        return 'Предпочтение';
      case 'schedule':
        return 'Привычка';
      default:
        return 'Заметка';
    }
  }

  /// Подстрока — сопровождение для humanLabel.
  String get humanSubtitle {
    String s(String k) => (value[k]?.toString() ?? '').trim();
    switch (kind) {
      case 'person':
        final parts = <String>[];
        final role = s('role');
        final age = s('age');
        final details = s('details');
        if (role.isNotEmpty) parts.add(role);
        if (age.isNotEmpty) parts.add('$age лет');
        if (details.isNotEmpty) parts.add(details);
        return parts.join(' · ');
      case 'place':
        return s('address');
      case 'preference':
        return '';
      case 'schedule':
        return s('when');
      default:
        return value.entries
            .where((e) => e.value is String && (e.value as String).isNotEmpty)
            .map((e) => e.value)
            .join(', ');
    }
  }

  /// Старое API — оставлено для совместимости.
  String get valueBrief => humanLabel;
}
