import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/features/moments/data/models/moment.dart';
import 'package:voicenote_ai/features/moments/data/repositories/moments_repository.dart';

/// Today-feed (≤ 50 ближайших на сутки + без времени). PRODUCT_PLAN.md §2.3.
final todayProvider = FutureProvider.autoDispose<List<Moment>>((ref) async {
  final repo = ref.watch(momentsRepositoryProvider);
  final list = await repo.list(view: 'today', limit: 50);
  return list.items;
});

/// Timeline пагинация — PRODUCT_PLAN.md §2.4. Простая `keep-state` реализация:
/// первая страница приходит автоматически; `loadMore()` догружает следующую
/// до тех пор, пока не отдадут пустой `next_cursor`.
class TimelineState {
  const TimelineState({
    required this.items,
    required this.isLoading,
    this.cursor,
    this.error,
    this.exhausted = false,
  });

  final List<Moment> items;
  final bool isLoading;
  final int? cursor;
  final Object? error;
  final bool exhausted;

  TimelineState copyWith({
    List<Moment>? items,
    bool? isLoading,
    int? cursor,
    Object? error,
    bool? exhausted,
    bool clearError = false,
  }) =>
      TimelineState(
        items: items ?? this.items,
        isLoading: isLoading ?? this.isLoading,
        cursor: cursor ?? this.cursor,
        error: clearError ? null : (error ?? this.error),
        exhausted: exhausted ?? this.exhausted,
      );

  static const initial = TimelineState(items: [], isLoading: true);
}

class TimelineController extends StateNotifier<TimelineState> {
  TimelineController(this._ref) : super(TimelineState.initial) {
    _refresh(reset: true);
  }

  final Ref _ref;
  MomentsRepository get _repo => _ref.read(momentsRepositoryProvider);

  Future<void> _refresh({required bool reset}) async {
    if (state.isLoading && !reset) return;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final cur = reset ? null : state.cursor;
      final page = await _repo.list(view: 'timeline', cursor: cur, limit: 50);
      final merged = reset ? page.items : [...state.items, ...page.items];
      state = TimelineState(
        items: merged,
        isLoading: false,
        cursor: page.nextCursor,
        exhausted: page.nextCursor == null,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e);
    }
  }

  Future<void> refresh() => _refresh(reset: true);
  Future<void> loadMore() {
    if (state.exhausted) return Future.value();
    return _refresh(reset: false);
  }
}

final timelineControllerProvider =
    StateNotifierProvider.autoDispose<TimelineController, TimelineState>(
  TimelineController.new,
);

/// Создание нового момента + инвалидация today/timeline. UI зовёт это после
/// возврата из voice-modal'а или текстового ввода.
final createMomentProvider = Provider<Future<Moment> Function({
  required String rawText,
  String source,
  String? clientId,
})>((ref) {
  return ({required String rawText, String source = 'text', String? clientId}) async {
    final repo = ref.read(momentsRepositoryProvider);
    final m = await repo.create(rawText: rawText, source: source, clientId: clientId);
    ref.invalidate(todayProvider);
    ref.read(timelineControllerProvider.notifier).refresh();
    return m;
  };
});
