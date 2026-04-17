import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/presentation/widgets/auth_form_field.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _obscure = true;
  bool _loading = false;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    try {
      await ref.read(sessionControllerProvider.notifier).register(
            email: _email.text,
            password: _password.text,
            firstName: _name.text,
          );
    } on ApiException catch (e) {
      if (mounted) _snack(e.message, isError: true);
    } catch (_) {
      if (mounted) _snack('Неожиданная ошибка. Попробуйте снова.', isError: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _snack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? Theme.of(context).colorScheme.error : null,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Регистрация')),
      body: SafeArea(
        child: AutofillGroup(
          child: Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
              children: [
                AuthFormField(
                  controller: _name,
                  label: 'Имя',
                  hintText: 'Как к вам обращаться',
                  prefixIcon: Icons.person_outline,
                  autofillHints: const [AutofillHints.givenName],
                  validator: (v) {
                    if ((v ?? '').trim().isEmpty) return 'Введите имя';
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                AuthFormField(
                  controller: _email,
                  label: 'Email',
                  hintText: 'you@example.com',
                  keyboardType: TextInputType.emailAddress,
                  prefixIcon: Icons.alternate_email,
                  autofillHints: const [AutofillHints.email, AutofillHints.newUsername],
                  validator: (v) {
                    final t = v?.trim() ?? '';
                    if (t.isEmpty) return 'Введите email';
                    if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(t)) {
                      return 'Некорректный email';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                AuthFormField(
                  controller: _password,
                  label: 'Пароль',
                  hintText: 'Минимум 8 символов',
                  obscureText: _obscure,
                  prefixIcon: Icons.lock_outline,
                  suffixIcon: _obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                  onSuffixTap: () => setState(() => _obscure = !_obscure),
                  autofillHints: const [AutofillHints.newPassword],
                  validator: (v) {
                    final t = v ?? '';
                    if (t.length < 8) return 'Минимум 8 символов';
                    if (!RegExp(r'[A-Za-z]').hasMatch(t)) return 'Нужна хотя бы одна буква';
                    if (!RegExp(r'\d').hasMatch(t)) return 'Нужна хотя бы одна цифра';
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                AuthFormField(
                  controller: _confirm,
                  label: 'Повторите пароль',
                  obscureText: _obscure,
                  prefixIcon: Icons.lock_outline,
                  textInputAction: TextInputAction.done,
                  validator: (v) {
                    if (v != _password.text) return 'Пароли не совпадают';
                    return null;
                  },
                ),
                const SizedBox(height: 28),
                FilledButton(
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Создать аккаунт'),
                ),
                const SizedBox(height: 12),
                Text(
                  'Создавая аккаунт, вы соглашаетесь с условиями использования и политикой конфиденциальности.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
