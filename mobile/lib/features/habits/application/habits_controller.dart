import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/features/habits/data/models/habit.dart';
import 'package:voicenote_ai/features/habits/data/repositories/habits_repository.dart';

final habitsListProvider =
    FutureProvider.autoDispose<List<Habit>>((ref) async {
  final repo = ref.watch(habitsRepositoryProvider);
  return repo.list();
});

final habitWeeklyStatsProvider =
    FutureProvider.family.autoDispose<List<HabitDailyStat>, int>((ref, habitId) {
  return ref.watch(habitsRepositoryProvider).weeklyStats(habitId);
});

class HabitsActions {
  HabitsActions(this._ref);
  final Ref _ref;

  Future<void> track(int id, HabitTrackStatus status) async {
    await _ref.read(habitsRepositoryProvider).track(id, status);
    _ref.invalidate(habitsListProvider);
    _ref.invalidate(habitWeeklyStatsProvider(id));
  }

  Future<List<Habit>> create(String text) async {
    final created = await _ref.read(habitsRepositoryProvider).createFromText(text);
    _ref.invalidate(habitsListProvider);
    return created;
  }

  Future<void> delete(int id) async {
    await _ref.read(habitsRepositoryProvider).delete(id);
    _ref.invalidate(habitsListProvider);
  }
}

final habitsActionsProvider = Provider<HabitsActions>(HabitsActions.new);
