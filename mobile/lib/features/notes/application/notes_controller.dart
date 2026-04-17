import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';

@immutable
class NotesListState {
  const NotesListState({
    required this.segment,
    required this.items,
    required this.page,
    required this.totalPages,
    required this.isLoading,
    required this.isLoadingMore,
    this.error,
  });

  final NotesSegment segment;
  final List<Note> items;
  final int page;
  final int totalPages;
  final bool isLoading;
  final bool isLoadingMore;
  final Object? error;

  bool get hasMore => page < totalPages;

  const NotesListState.initial(this.segment)
      : items = const [],
        page = 0,
        totalPages = 0,
        isLoading = true,
        isLoadingMore = false,
        error = null;

  NotesListState copyWith({
    NotesSegment? segment,
    List<Note>? items,
    int? page,
    int? totalPages,
    bool? isLoading,
    bool? isLoadingMore,
    Object? error,
    bool clearError = false,
  }) =>
      NotesListState(
        segment: segment ?? this.segment,
        items: items ?? this.items,
        page: page ?? this.page,
        totalPages: totalPages ?? this.totalPages,
        isLoading: isLoading ?? this.isLoading,
        isLoadingMore: isLoadingMore ?? this.isLoadingMore,
        error: clearError ? null : (error ?? this.error),
      );
}

class NotesController extends StateNotifier<NotesListState> {
  NotesController(this._repo, NotesSegment segment)
      : super(NotesListState.initial(segment)) {
    refresh();
  }

  final NotesRepository _repo;

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final page = await _repo.list(segment: state.segment, page: 1);
      state = state.copyWith(
        items: page.items,
        page: page.page,
        totalPages: page.totalPages,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e);
    }
  }

  Future<void> loadMore() async {
    if (!state.hasMore || state.isLoadingMore) return;
    state = state.copyWith(isLoadingMore: true);
    try {
      final page = await _repo.list(segment: state.segment, page: state.page + 1);
      state = state.copyWith(
        items: [...state.items, ...page.items],
        page: page.page,
        totalPages: page.totalPages,
        isLoadingMore: false,
      );
    } catch (e) {
      state = state.copyWith(isLoadingMore: false, error: e);
    }
  }

  Future<void> archiveLocal(int id) async {
    state = state.copyWith(
      items: state.items.where((n) => n.id != id).toList(growable: false),
    );
  }

  Future<void> deleteNote(int id) async {
    final backup = state.items;
    await archiveLocal(id);
    try {
      await _repo.delete(id);
    } catch (e) {
      state = state.copyWith(items: backup, error: e);
      rethrow;
    }
  }

  Future<void> completeNote(int id) async {
    try {
      final updated = await _repo.complete(id);
      state = state.copyWith(
        items: state.items.map((n) => n.id == id ? updated : n).toList(growable: false),
      );
    } catch (e) {
      state = state.copyWith(error: e);
      rethrow;
    }
  }

  void upsert(Note note) {
    final list = [...state.items];
    final idx = list.indexWhere((n) => n.id == note.id);
    if (idx == -1) {
      list.insert(0, note);
    } else {
      list[idx] = note;
    }
    state = state.copyWith(items: list);
  }
}

final notesControllerProvider = StateNotifierProvider.family<
    NotesController, NotesListState, NotesSegment>(
  (ref, segment) => NotesController(ref.watch(notesRepositoryProvider), segment),
);
