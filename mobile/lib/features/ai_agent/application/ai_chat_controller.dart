import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/features/ai_agent/data/models/chat_message.dart';
import 'package:voicenote_ai/features/ai_agent/data/repositories/ai_repository.dart';

@immutable
class AiChatState {
  const AiChatState({
    required this.messages,
    required this.isLoadingHistory,
    required this.isSending,
    this.error,
  });

  final List<ChatMessage> messages;
  final bool isLoadingHistory;
  final bool isSending;
  final Object? error;

  const AiChatState.initial()
      : messages = const [],
        isLoadingHistory = true,
        isSending = false,
        error = null;

  AiChatState copyWith({
    List<ChatMessage>? messages,
    bool? isLoadingHistory,
    bool? isSending,
    Object? error,
    bool clearError = false,
  }) =>
      AiChatState(
        messages: messages ?? this.messages,
        isLoadingHistory: isLoadingHistory ?? this.isLoadingHistory,
        isSending: isSending ?? this.isSending,
        error: clearError ? null : (error ?? this.error),
      );
}

class AiChatController extends StateNotifier<AiChatState> {
  AiChatController(this._repo) : super(const AiChatState.initial()) {
    _loadHistory();
  }

  final AiRepository _repo;

  Future<void> _loadHistory() async {
    try {
      final history = await _repo.history();
      state = state.copyWith(messages: history, isLoadingHistory: false);
    } catch (e) {
      state = state.copyWith(isLoadingHistory: false, error: e);
    }
  }

  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    final now = DateTime.now();
    final userMsg = ChatMessage(
      id: '${now.microsecondsSinceEpoch}',
      role: ChatRole.user,
      content: trimmed,
      createdAt: now,
    );
    state = state.copyWith(
      messages: [...state.messages, userMsg],
      isSending: true,
      clearError: true,
    );

    try {
      final reply = await _repo.send(trimmed);
      final assistantMsg = ChatMessage(
        id: '${DateTime.now().microsecondsSinceEpoch}',
        role: ChatRole.assistant,
        content: reply,
        createdAt: DateTime.now(),
      );
      state = state.copyWith(
        messages: [...state.messages, assistantMsg],
        isSending: false,
      );
    } catch (e) {
      state = state.copyWith(isSending: false, error: e);
    }
  }

  Future<void> clear() async {
    await _repo.reset();
    state = state.copyWith(messages: const []);
  }
}

final aiChatProvider =
    StateNotifierProvider.autoDispose<AiChatController, AiChatState>(
  (ref) => AiChatController(ref.watch(aiRepositoryProvider)),
);
