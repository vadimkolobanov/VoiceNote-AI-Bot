import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/presentation/widgets/auth_form_field.dart';

/// S5 — Auth-экран (PRODUCT_PLAN.md §2.2). Email/password регистрация и вход.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  bool _isRegister = false;
  bool _busy = false;

  final _emailCtl = TextEditingController();
  final _passCtl = TextEditingController();
  final _nameCtl = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  @override
  void dispose() {
    _emailCtl.dispose();
    _passCtl.dispose();
    _nameCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      final notifier = ref.read(sessionControllerProvider.notifier);
      if (_isRegister) {
        await notifier.register(
          email: _emailCtl.text,
          password: _passCtl.text,
          displayName: _nameCtl.text.trim().isEmpty ? null : _nameCtl.text,
        );
      } else {
        await notifier.login(email: _emailCtl.text, password: _passCtl.text);
      }
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (e) {
      _toast('Что-то пошло не так. $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
            children: [
              Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                  gradient: MX.brandGradient,
                  borderRadius: BorderRadius.circular(MX.rXl),
                  boxShadow: MX.fabGlow,
                ),
                child: const Center(
                  child: Text('М',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 44,
                          fontWeight: FontWeight.w700)),
                ),
              ),
              const SizedBox(height: 32),
              Text(_isRegister ? 'Создаём аккаунт' : 'С возвращением',
                  style: Theme.of(context).textTheme.displaySmall),
              const SizedBox(height: 8),
              Text(
                _isRegister
                    ? 'Зарегистрируйся — и я начну тебя помнить.'
                    : 'Войди и я покажу что ты успел рассказать.',
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: MX.fgMuted),
              ),
              const SizedBox(height: 36),
              _ModeSwitch(
                isRegister: _isRegister,
                onChanged: _busy ? null : (v) => setState(() => _isRegister = v),
              ),
              const SizedBox(height: 24),
              if (_isRegister) ...[
                AuthFormField(
                  controller: _nameCtl,
                  label: 'Имя',
                  hintText: 'Как тебя называть',
                  prefixIcon: Icons.person_outline,
                  autofillHints: const [AutofillHints.givenName],
                ),
                const SizedBox(height: 12),
              ],
              AuthFormField(
                controller: _emailCtl,
                label: 'Email',
                hintText: 'name@example.com',
                keyboardType: TextInputType.emailAddress,
                prefixIcon: Icons.alternate_email,
                autofillHints: const [AutofillHints.email],
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return 'Введи email';
                  if (!v.contains('@') || !v.contains('.')) return 'Странный email';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              AuthFormField(
                controller: _passCtl,
                label: 'Пароль',
                hintText: _isRegister ? 'не короче 8 символов' : '',
                obscureText: true,
                prefixIcon: Icons.lock_outline,
                textInputAction: TextInputAction.done,
                autofillHints: _isRegister
                    ? const [AutofillHints.newPassword]
                    : const [AutofillHints.password],
                validator: (v) {
                  if (v == null || v.isEmpty) return 'Введи пароль';
                  if (_isRegister && v.length < 8) return 'Минимум 8 символов';
                  return null;
                },
              ),
              const SizedBox(height: 28),
              SizedBox(
                height: 52,
                child: FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: Text(
                    _busy
                        ? '...'
                        : (_isRegister ? 'Создать аккаунт' : 'Войти'),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              if (!_isRegister)
                Center(
                  child: TextButton(
                    onPressed: _busy
                        ? null
                        : () => _toast('Восстановление пароля появится скоро'),
                    child: const Text('Забыл пароль'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ModeSwitch extends StatelessWidget {
  const _ModeSwitch({required this.isRegister, required this.onChanged});

  final bool isRegister;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rFull),
        border: Border.all(color: MX.line),
      ),
      child: Row(
        children: [
          _segment(context, 'Войти', !isRegister, false),
          _segment(context, 'Создать', isRegister, true),
        ],
      ),
    );
  }

  Widget _segment(BuildContext context, String label, bool active, bool toRegister) {
    return Expanded(
      child: Material(
        color: active ? MX.fg : Colors.transparent,
        borderRadius: BorderRadius.circular(MX.rFull),
        child: InkWell(
          borderRadius: BorderRadius.circular(MX.rFull),
          onTap: onChanged == null ? null : () => onChanged!(toRegister),
          child: Container(
            height: 40,
            alignment: Alignment.center,
            child: Text(
              label,
              style: TextStyle(
                color: active ? MX.bgBase : MX.fgMuted,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
