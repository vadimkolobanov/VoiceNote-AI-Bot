import 'package:flutter/foundation.dart';

/// Moment — отражает `MomentOut` из backend `/api/v1/moments` (PRODUCT_PLAN.md
/// §4.1, §5.3). Никаких freezed/codegen — handwritten fromJson/toJson по §7.1.
@immutable
class Moment {
  const Moment({
    required this.id,
    required this.rawText,
    required this.title,
    required this.facets,
    required this.status,
    required this.source,
    required this.createdVia,
    required this.createdAtIso,
    required this.updatedAtIso,
    this.clientId,
    this.summary,
    this.occursAtIso,
    this.rrule,
    this.rruleUntilIso,
    this.audioUrl,
  });

  final int id;
  final String? clientId;
  final String rawText;
  final String title;
  final String? summary;
  final Map<String, dynamic> facets;
  final String? occursAtIso;
  final String? rrule;
  final String? rruleUntilIso;
  final String status; // 'active' | 'done' | 'archived' | 'trashed'
  final String source; // 'voice' | 'text' | 'forward' | 'alice' | 'manual'
  final String? audioUrl;
  final String createdAtIso;
  final String updatedAtIso;
  final String createdVia;

  // ── derived ────────────────────────────────────────────────────────────
  String get kind => (facets['kind'] as String?) ?? 'note';

  DateTime? get occursAt =>
      occursAtIso == null ? null : DateTime.tryParse(occursAtIso!)?.toLocal();
  DateTime get createdAt =>
      DateTime.tryParse(createdAtIso)?.toLocal() ?? DateTime.now();

  bool get hasReminder => occursAt != null;
  bool get isDone => status == 'done';
  bool get isActive => status == 'active';

  factory Moment.fromJson(Map<String, dynamic> json) => Moment(
        id: (json['id'] as num).toInt(),
        clientId: json['client_id'] as String?,
        rawText: (json['raw_text'] as String?) ?? '',
        title: (json['title'] as String?) ?? '',
        summary: json['summary'] as String?,
        facets:
            (json['facets'] as Map<String, dynamic>?) ?? const <String, dynamic>{},
        occursAtIso: json['occurs_at'] as String?,
        rrule: json['rrule'] as String?,
        rruleUntilIso: json['rrule_until'] as String?,
        status: (json['status'] as String?) ?? 'active',
        source: (json['source'] as String?) ?? 'text',
        audioUrl: json['audio_url'] as String?,
        createdAtIso: (json['created_at'] as String?) ?? '',
        updatedAtIso: (json['updated_at'] as String?) ?? '',
        createdVia: (json['created_via'] as String?) ?? 'mobile',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'client_id': clientId,
        'raw_text': rawText,
        'title': title,
        'summary': summary,
        'facets': facets,
        'occurs_at': occursAtIso,
        'rrule': rrule,
        'rrule_until': rruleUntilIso,
        'status': status,
        'source': source,
        'audio_url': audioUrl,
        'created_at': createdAtIso,
        'updated_at': updatedAtIso,
        'created_via': createdVia,
      };

  Moment copyWith({
    String? title,
    String? summary,
    String? occursAtIso,
    String? rrule,
    String? rruleUntilIso,
    String? status,
    Map<String, dynamic>? facets,
  }) =>
      Moment(
        id: id,
        clientId: clientId,
        rawText: rawText,
        title: title ?? this.title,
        summary: summary ?? this.summary,
        facets: facets ?? this.facets,
        occursAtIso: occursAtIso ?? this.occursAtIso,
        rrule: rrule ?? this.rrule,
        rruleUntilIso: rruleUntilIso ?? this.rruleUntilIso,
        status: status ?? this.status,
        source: source,
        audioUrl: audioUrl,
        createdAtIso: createdAtIso,
        updatedAtIso: updatedAtIso,
        createdVia: createdVia,
      );
}
