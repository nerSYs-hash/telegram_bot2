#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for Trigger Validation System
Проверка работы триггеров "богач" и "активист"
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTriggerValidation(unittest.TestCase):
    """Test suite for trigger validation functions"""
    
    @staticmethod
    def is_single_word(text: str) -> bool:
        """Проверка что текст - одно слово"""
        return len(text.strip().split()) == 1
    
    @staticmethod
    def has_forbidden_words(text: str) -> bool:
        """Проверка на запрещённые слова"""
        forbidden = [
            'я', 'ты', 'он', 'она', 'мы', 'вы', 'они',
            'мой', 'твой', 'его', 'её', 'наш', 'ваш', 'их',
            'этот', 'тот', 'такой', 'эта', 'та', 'такая',
            'самый', 'главный', 'настоящий', 'супер', 'крутой'
        ]
        words = text.lower().split()
        return any(word in forbidden for word in words)
    
    @staticmethod
    def is_valid_single_trigger(text: str, trigger: str) -> bool:
        """Многоуровневая проверка триггера"""
        text_clean = text.strip().lower()
        
        # Уровень 1: Точное совпадение
        if text_clean != trigger:
            return False
        
        # Уровень 2: Только одно слово
        if not TestTriggerValidation.is_single_word(text):
            return False
        
        # Уровень 3: Нет запрещённых слов
        if TestTriggerValidation.has_forbidden_words(text):
            return False
        
        return True
    
    # ============================================
    # ТЕСТЫ ДЛЯ ТРИГГЕРА "БОГАЧ"
    # ============================================
    
    def test_bogach_exact_match(self):
        """<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Точное совпадение 'богач' должно работать"""
        self.assertTrue(self.is_valid_single_trigger('богач', 'богач'))
    
    def test_bogach_case_insensitive(self):
        """<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Регистр не важен"""
        self.assertTrue(self.is_valid_single_trigger('Богач', 'богач'))
        self.assertTrue(self.is_valid_single_trigger('БОГАЧ', 'богач'))
        self.assertTrue(self.is_valid_single_trigger('БоГаЧ', 'богач'))
    
    def test_bogach_with_spaces(self):
        """<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Пробелы игнорируются"""
        self.assertTrue(self.is_valid_single_trigger('  богач  ', 'богач'))
        self.assertTrue(self.is_valid_single_trigger('\tbогач\n', 'богач'))
    
    def test_bogach_with_pronoun_ty(self):
        """❌ 'ты богач' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('ты богач', 'богач'))
    
    def test_bogach_with_pronoun_ya(self):
        """❌ 'я богач' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('я богач', 'богач'))
    
    def test_bogach_with_pronoun_on(self):
        """❌ 'он богач' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('он богач', 'богач'))
    
    def test_bogach_plural(self):
        """❌ 'богачи' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('богачи', 'богач'))
    
    def test_bogach_genitive(self):
        """❌ 'богача' (родительный падеж) НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('богача', 'богач'))
    
    def test_bogach_dative(self):
        """❌ 'богачу' (дательный падеж) НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('богачу', 'богач'))
    
    def test_bogach_with_adjective(self):
        """❌ 'настоящий богач' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('настоящий богач', 'богач'))
        self.assertFalse(self.is_valid_single_trigger('супер богач', 'богач'))
        self.assertFalse(self.is_valid_single_trigger('крутой богач', 'богач'))
    
    # ============================================
    # ТЕСТЫ ДЛЯ ТРИГГЕРА "АКТИВИСТ"
    # ============================================
    
    def test_activist_exact_match(self):
        """<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Точное совпадение 'активист' должно работать"""
        self.assertTrue(self.is_valid_single_trigger('активист', 'активист'))
    
    def test_activist_case_insensitive(self):
        """<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Регистр не важен"""
        self.assertTrue(self.is_valid_single_trigger('Активист', 'активист'))
        self.assertTrue(self.is_valid_single_trigger('АКТИВИСТ', 'активист'))
    
    def test_activist_with_pronoun_ya(self):
        """❌ 'я активист' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('я активист', 'активист'))
    
    def test_activist_with_pronoun_ty(self):
        """❌ 'ты активист' НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('ты активист', 'активист'))
    
    def test_activist_genitive(self):
        """❌ 'активиста' (родительный падеж) НЕ должно срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('активиста', 'активист'))
    
    def test_activist_with_phrase(self):
        """❌ Фразы с 'активист' НЕ должны срабатывать"""
        self.assertFalse(self.is_valid_single_trigger('настоящий активист', 'активист'))
        self.assertFalse(self.is_valid_single_trigger('я топ активист', 'активист'))
        self.assertFalse(self.is_valid_single_trigger('супер активист', 'активист'))
    
    # ============================================
    # ТЕСТЫ ВСПОМОГАТЕЛЬНЫХ ФУНКЦИЙ
    # ============================================
    
    def test_is_single_word_true(self):
        """Проверка одиночных слов"""
        self.assertTrue(self.is_single_word('богач'))
        self.assertTrue(self.is_single_word('активист'))
        self.assertTrue(self.is_single_word('  топ  '))
    
    def test_is_single_word_false(self):
        """Проверка что фразы не одиночные слова"""
        self.assertFalse(self.is_single_word('ты богач'))
        self.assertFalse(self.is_single_word('я активист'))
        self.assertFalse(self.is_single_word('топ богачей'))
    
    def test_has_forbidden_words_pronouns(self):
        """Проверка обнаружения местоимений"""
        self.assertTrue(self.has_forbidden_words('я богач'))
        self.assertTrue(self.has_forbidden_words('ты активист'))
        self.assertTrue(self.has_forbidden_words('он богач чата'))
        self.assertFalse(self.has_forbidden_words('богач'))
        self.assertFalse(self.has_forbidden_words('активист'))
    
    def test_has_forbidden_words_adjectives(self):
        """Проверка обнаружения прилагательных"""
        self.assertTrue(self.has_forbidden_words('настоящий богач'))
        self.assertTrue(self.has_forbidden_words('супер активист'))
        self.assertTrue(self.has_forbidden_words('главный богач'))
        self.assertFalse(self.has_forbidden_words('топ богачей'))
    
    # ============================================
    # ТЕСТЫ EDGE CASES
    # ============================================
    
    def test_empty_string(self):
        """Пустая строка"""
        self.assertFalse(self.is_valid_single_trigger('', 'богач'))
        self.assertFalse(self.is_valid_single_trigger('   ', 'богач'))
    
    def test_special_characters(self):
        """Специальные символы"""
        self.assertFalse(self.is_valid_single_trigger('богач!', 'богач'))
        self.assertFalse(self.is_valid_single_trigger('богач?', 'богач'))
        self.assertFalse(self.is_valid_single_trigger('богач.', 'богач'))
    
    def test_mixed_case_pronouns(self):
        """Местоимения с разным регистром"""
        self.assertFalse(self.is_valid_single_trigger('Я богач', 'богач'))
        self.assertFalse(self.is_valid_single_trigger('ТЫ активист', 'активист'))


class TestWhitelistTriggers(unittest.TestCase):
    """Test whitelist triggers for multi-word phrases"""
    
    def test_rich_whitelist(self):
        """Проверка whitelist для богачей"""
        allowed_rich = [
            'топ', 'топ богачей', 'топ 5', 'топ5', 'топ-5',
            'топ богачей 5', 'рейтинг богачей', 'список богачей'
        ]
        
        # Эти ДОЛЖНЫ работать
        for trigger in allowed_rich:
            self.assertIn(trigger, allowed_rich, f"'{trigger}' должен быть в whitelist")
        
        # Эти НЕ должны работать
        not_allowed = ['покажи топ', 'дай топ', 'хочу топ богачей']
        for phrase in not_allowed:
            self.assertNotIn(phrase, allowed_rich, f"'{phrase}' НЕ должен быть в whitelist")
    
    def test_activist_whitelist(self):
        """Проверка whitelist для активистов"""
        allowed_activist = [
            'топ активистов', 'топ активист', 'топ 5 активистов',
            'топ5 активистов', 'топ-5 активистов', 'активисты',
            'активные', 'рейтинг активистов', 'список активистов'
        ]
        
        # Эти ДОЛЖНЫ работать
        for trigger in allowed_activist:
            self.assertIn(trigger, allowed_activist, f"'{trigger}' должен быть в whitelist")
        
        # Эти НЕ должны работать
        not_allowed = ['я топ активист', 'покажи активистов', 'дай активных']
        for phrase in not_allowed:
            self.assertNotIn(phrase, allowed_activist, f"'{phrase}' НЕ должен быть в whitelist")


def run_tests():
    """Run all tests and print results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTriggerValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestWhitelistTriggers))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*70)
    print(f"<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Успешно: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Провалено: {len(result.failures)}")
    print(f"⚠️  Ошибки: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
