"""
Intelligent Audio Mapper for IVR Code Generation
Converts text to audio file IDs using learned patterns from the audio database

Add this as: intelligent_audio_mapper.py
"""

import re
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MappingResult:
    """Result of text-to-audio mapping"""
    play_prompt: List[str]
    play_log: str
    missing_segments: List[str]
    confidence_score: float
    grammar_applied: bool = False

class GrammarEngine:
    """Handles grammatical rules for audio file selection"""
    
    def __init__(self, audio_database):
        self.audio_db = audio_database
        self.vowel_words = set()
        self.consonant_words = set()
        self._learn_grammar_patterns()
    
    def _learn_grammar_patterns(self):
        """Learn grammar patterns from the audio database"""
        try:
            df = self.audio_db.get_dataframe()
            
            # Learn from callout_type and job_classification folders
            callout_data = df[df['Folder'].isin(['callout_type', 'job_classification'])]
            
            for _, row in callout_data.iterrows():
                transcript = row['Transcript'].lower().strip()
                words = transcript.split()
                
                for word in words:
                    if len(word) > 2:  # Skip very short words
                        if word[0] in 'aeiou':
                            self.vowel_words.add(word)
                        else:
                            self.consonant_words.add(word)
            
            # Add some common patterns if not found in data
            default_vowel_words = {'electric', 'emergency', 'important', 'urgent', 'overtime'}
            default_consonant_words = {'normal', 'regular', 'storm', 'planned', 'maintenance'}
            
            self.vowel_words.update(default_vowel_words)
            self.consonant_words.update(default_consonant_words)
            
            logger.info(f"Grammar engine learned {len(self.vowel_words)} vowel sounds, "
                       f"{len(self.consonant_words)} consonant sounds")
            
        except Exception as e:
            logger.warning(f"Could not learn grammar patterns: {e}. Using defaults.")
            # Use defaults if learning fails
            self.vowel_words = {'electric', 'emergency', 'important', 'urgent', 'overtime'}
            self.consonant_words = {'normal', 'regular', 'storm', 'planned', 'maintenance'}
    
    def requires_an(self, next_word: str) -> bool:
        """Determine if 'an' should be used instead of 'a'"""
        if not next_word:
            return False
        
        word_lower = next_word.lower().strip()
        
        # Check learned vowel sound words
        if word_lower in self.vowel_words:
            return True
            
        # Check learned consonant sound words  
        if word_lower in self.consonant_words:
            return False
            
        # Default rule: starts with vowel letter
        return word_lower[0] in 'aeiou'

class TextSegmenter:
    """Intelligently segments text into audio file components"""
    
    def __init__(self, audio_database, grammar_engine):
        self.audio_db = audio_database
        self.grammar = grammar_engine
        self._discover_common_phrases()
    
    def _discover_common_phrases(self):
        """Discover common phrases from the database"""
        self.common_phrases = {}
        
        try:
            df = self.audio_db.get_dataframe()
            
            # Find frequently used instruction phrases
            instruction_patterns = [
                'press', 'if this is', 'you need more time', 'is not home',
                'to repeat', 'are you available', 'thank you', 'goodbye',
                'this is an', 'this is a', 'callout from', 'enter your'
            ]
            
            for pattern in instruction_patterns:
                matches = df[df['Transcript'].str.contains(pattern, case=False, na=False)]
                if not matches.empty:
                    # Take the first match for this pattern
                    match = matches.iloc[0]
                    audio_id = match['File Name'].replace('.ulaw', '')
                    folder = match['Folder']
                    self.common_phrases[pattern] = f"{folder}:{audio_id}"
            
            logger.info(f"Discovered {len(self.common_phrases)} common phrases")
            
        except Exception as e:
            logger.warning(f"Could not discover common phrases: {e}")
            self.common_phrases = {}
    
    def segment_text(self, text: str, company: str = None) -> List[Tuple[str, str, float]]:
        """
        Break text into segments that can be mapped to audio files
        Returns list of (text_segment, segment_type, confidence) tuples
        """
        segments = []
        remaining_text = text.lower().strip()
        
        # Remove common punctuation but preserve structure
        remaining_text = re.sub(r'[.,!?;]', '', remaining_text)
        
        while remaining_text:
            found_segment = False
            
            # 1. Try exact database matches for decreasing word lengths
            words = remaining_text.split()
            if not words:
                break
                
            for word_count in range(min(6, len(words)), 0, -1):
                phrase = ' '.join(words[:word_count])
                matches = self.audio_db.find_exact_match(phrase, company)
                
                if matches:
                    segments.append((phrase, 'database_match', 1.0))
                    remaining_text = ' '.join(words[word_count:])
                    found_segment = True
                    break
            
            if found_segment:
                continue
            
            # 2. Try discovered common phrases
            phrase_found = False
            for phrase in sorted(self.common_phrases.keys(), key=len, reverse=True):
                if remaining_text.startswith(phrase):
                    segments.append((phrase, 'common_phrase', 0.9))
                    remaining_text = remaining_text[len(phrase):].strip()
                    phrase_found = True
                    break
            
            if phrase_found:
                continue
            
            # 3. Look for dynamic patterns
            # Variables in parentheses
            var_match = re.search(r'\((.*?)\)', remaining_text)
            if var_match:
                before_var = remaining_text[:var_match.start()].strip()
                var_content = var_match.group(1)
                
                if before_var:
                    segments.append((before_var, 'text_fragment', 0.7))
                
                segments.append((var_content, 'dynamic_variable', 0.9))
                remaining_text = remaining_text[var_match.end():].strip()
                continue
            
            # Numbers (for digits, PIN entry, etc.)
            digit_match = re.search(r'\b(\d+)\b', remaining_text)
            if digit_match:
                before_digit = remaining_text[:digit_match.start()].strip()
                digit = digit_match.group(1)
                
                if before_digit:
                    segments.append((before_digit, 'text_fragment', 0.7))
                
                segments.append((digit, 'digit', 0.9))
                remaining_text = remaining_text[digit_match.end():].strip()
                continue
            
            # Level patterns (Level 2, Level 3, etc.)
            level_match = re.search(r'\b(level\s+\d+)\b', remaining_text)
            if level_match:
                before_level = remaining_text[:level_match.start()].strip()
                level = level_match.group(1)
                
                if before_level:
                    segments.append((before_level, 'text_fragment', 0.7))
                
                segments.append((level, 'location_variable', 0.9))
                remaining_text = remaining_text[level_match.end():].strip()
                continue
            
            # 4. Take first word as unknown segment
            if words:
                segments.append((words[0], 'unknown', 0.3))
                remaining_text = ' '.join(words[1:])
            else:
                break
        
        return segments

class IntelligentAudioMapper:
    """Main class that converts text to audio file IDs using learned patterns"""
    
    def __init__(self, audio_database):
        self.audio_db = audio_database
        self.grammar = GrammarEngine(audio_database)
        self.segmenter = TextSegmenter(audio_database, self.grammar)
        
        # Learn default error prompts per company
        self._discover_default_prompts()
    
    def _discover_default_prompts(self):
        """Discover default error and timeout prompts from database"""
        self.default_prompts = {}
        
        try:
            df = self.audio_db.get_dataframe()
            companies = df['Company'].unique()
            
            for company in companies:
                company_data = df[df['Company'] == company]
                
                # Find error prompts
                error_matches = company_data[
                    company_data['Transcript'].str.contains(
                        'error|invalid|try again|sorry', case=False, na=False
                    )
                ]
                
                error_prompt = 'callflow:1009'  # Default fallback
                if not error_matches.empty:
                    match = error_matches.iloc[0]
                    audio_id = match['File Name'].replace('.ulaw', '')
                    folder = match['Folder']
                    error_prompt = f"{folder}:{audio_id}"
                
                self.default_prompts[company] = {
                    'error_prompt': error_prompt,
                    'timeout_prompt': error_prompt  # Use same for timeout
                }
            
        except Exception as e:
            logger.warning(f"Could not discover default prompts: {e}")
            self.default_prompts = {}
    
    def map_text_to_audio(self, text: str, company: str = 'aep') -> MappingResult:
        """
        Convert text to IVR audio configuration using intelligent mapping
        
        Args:
            text: The text to convert
            company: Company context for schema hierarchy
        
        Returns:
            MappingResult with playPrompt array and metadata
        """
        
        # Try exact match first (highest confidence)
        exact_matches = self.audio_db.find_exact_match(text, company)
        if exact_matches:
            match = exact_matches[0]
            return MappingResult(
                play_prompt=[match['full_path']],
                play_log=text,
                missing_segments=[],
                confidence_score=1.0
            )
        
        # Intelligent segmentation
        segments = self.segmenter.segment_text(text, company)
        
        play_prompt = []
        play_log_parts = []
        missing_segments = []
        total_confidence = 0.0
        grammar_applied = False
        
        for i, (segment_text, segment_type, confidence) in enumerate(segments):
            
            if segment_type == 'database_match':
                # Direct match in database
                matches = self.audio_db.find_exact_match(segment_text, company)
                if matches:
                    match = matches[0]
                    play_prompt.append(match['full_path'])
                    play_log_parts.append(segment_text.title())
                    total_confidence += confidence
                else:
                    missing_segments.append(segment_text)
                    play_log_parts.append(f"[MISSING: {segment_text}]")
            
            elif segment_type == 'common_phrase':
                # Use discovered common phrase
                if segment_text in self.segmenter.common_phrases:
                    # Handle grammar rules for "this is a/an"
                    if segment_text in ['this is a', 'this is an']:
                        next_segment = segments[i + 1] if i + 1 < len(segments) else None
                        if next_segment:
                            next_text = next_segment[0]
                            should_use_an = self.grammar.requires_an(next_text)
                            
                            if should_use_an and segment_text == 'this is a':
                                # Find "this is an" version
                                an_matches = self.audio_db.find_exact_match('this is an', company)
                                if an_matches:
                                    play_prompt.append(an_matches[0]['full_path'])
                                    grammar_applied = True
                                else:
                                    play_prompt.append(self.segmenter.common_phrases[segment_text])
                            elif not should_use_an and segment_text == 'this is an':
                                # Find "this is a" version
                                a_matches = self.audio_db.find_exact_match('this is a', company)
                                if a_matches:
                                    play_prompt.append(a_matches[0]['full_path'])
                                    grammar_applied = True
                                else:
                                    play_prompt.append(self.segmenter.common_phrases[segment_text])
                            else:
                                play_prompt.append(self.segmenter.common_phrases[segment_text])
                        else:
                            play_prompt.append(self.segmenter.common_phrases[segment_text])
                    else:
                        play_prompt.append(self.segmenter.common_phrases[segment_text])
                    
                    play_log_parts.append(segment_text.title())
                    total_confidence += confidence
                else:
                    missing_segments.append(segment_text)
                    play_log_parts.append(f"[MISSING: {segment_text}]")
            
            elif segment_type == 'dynamic_variable':
                # Handle dynamic variables
                if 'employee' in segment_text.lower():
                    play_prompt.append("names:{{contact_id}}")
                    play_log_parts.append("[Employee Name]")
                elif 'location' in segment_text.lower():
                    play_prompt.append("location:{{callout_location}}")
                    play_log_parts.append("[Location]")
                elif any(word in segment_text.lower() for word in ['electric', 'normal', 'emergency']):
                    play_prompt.append("type:{{callout_type}}")
                    play_log_parts.append("[Callout Type]")
                else:
                    # Try to find in database
                    matches = self.audio_db.find_exact_match(segment_text, company)
                    if matches:
                        match = matches[0]
                        play_prompt.append(match['full_path'])
                        play_log_parts.append(segment_text.title())
                    else:
                        missing_segments.append(segment_text)
                        play_log_parts.append(f"[VARIABLE: {segment_text}]")
                
                total_confidence += confidence
            
            elif segment_type == 'location_variable':
                # Handle Level X patterns
                level_match = re.search(r'level\s+(\d+)', segment_text)
                if level_match:
                    level_num = level_match.group(1)
                    play_prompt.append(f"location:{{{{level{level_num}_location}}}}")
                    play_log_parts.append(f"[Level {level_num} Location]")
                else:
                    play_prompt.append("location:{{callout_location}}")
                    play_log_parts.append("[Location]")
                
                total_confidence += confidence
            
            elif segment_type == 'digit':
                # Handle digits/numbers
                play_prompt.append(f"digits:{segment_text}")
                play_log_parts.append(segment_text)
                total_confidence += confidence
            
            elif segment_type == 'text_fragment':
                # Try to find text fragments in database
                matches = self.audio_db.find_exact_match(segment_text, company)
                if matches:
                    match = matches[0]
                    play_prompt.append(match['full_path'])
                    play_log_parts.append(segment_text.title())
                    total_confidence += confidence
                else:
                    missing_segments.append(segment_text)
                    play_log_parts.append(f"[MISSING: {segment_text}]")
            
            else:  # unknown
                missing_segments.append(segment_text)
                play_log_parts.append(f"[UNKNOWN: {segment_text}]")
        
        # Calculate final confidence
        confidence_score = total_confidence / len(segments) if segments else 0.0
        
        # Format final output
        final_play_prompt = play_prompt if len(play_prompt) > 1 else (play_prompt[0] if play_prompt else "callflow:1351")
        final_play_log = ' '.join(play_log_parts)
        
        return MappingResult(
            play_prompt=final_play_prompt,
            play_log=final_play_log,
            missing_segments=missing_segments,
            confidence_score=confidence_score,
            grammar_applied=grammar_applied
        )
    
    def get_company_error_prompt(self, company: str) -> str:
        """Get company-specific error prompt"""
        return self.default_prompts.get(company, {}).get('error_prompt', 'callflow:1009')
    
    def get_mapping_stats(self) -> Dict[str, Any]:
        """Get statistics about the mapping system"""
        return {
            'total_audio_files': len(self.audio_db.get_dataframe()),
            'companies_supported': len(self.audio_db.get_companies()),
            'categories_available': len(self.audio_db.get_folders()),
            'common_phrases_learned': len(self.segmenter.common_phrases),
            'vowel_words_learned': len(self.grammar.vowel_words),
            'consonant_words_learned': len(self.grammar.consonant_words)
        }

# Example usage
if __name__ == "__main__":
    print("Intelligent Audio Mapper for IVR Code Generation")
    print("Add this file to your Streamlit app and import as:")
    print("from intelligent_audio_mapper import IntelligentAudioMapper")