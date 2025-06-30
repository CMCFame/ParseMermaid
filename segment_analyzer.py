"""
Intelligent Segment Analyzer and ID Mapper for IVR Code Generation
Converts Mermaid text into exact audio file ID mappings
"""

import pandas as pd
import re
import json
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from difflib import SequenceMatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AudioSegment:
    """Represents a mapped audio segment"""
    text: str
    file_id: str
    company: str
    folder: str
    confidence: float
    is_variable: bool = False
    variable_type: Optional[str] = None

@dataclass
class MappingResult:
    """Result of text-to-ID mapping"""
    original_text: str
    segments: List[AudioSegment]
    missing_segments: List[str]
    confidence_score: float
    requires_manual_review: bool

class GrammarRules:
    """Handles grammar rules for audio file selection"""
    
    VOWEL_SOUNDS = {'a', 'e', 'i', 'o', 'u'}
    VOWEL_SOUND_WORDS = {
        'electric', 'emergency', 'urgent', 'outage', 'equipment',
        'employee', 'engineer', 'operator', 'overtime', 'assembly'
    }
    
    A_AN_MAPPING = {
        'callflow:1191': 'an',  # "This is an"
        'callflow:1190': 'a',   # "This is a"
    }
    
    @classmethod
    def needs_an_article(cls, next_word: str) -> bool:
        """Determine if 'an' vs 'a' should be used"""
        if not next_word:
            return False
        
        next_word = next_word.lower().strip()
        
        # Check specific words that sound like vowels
        if next_word in cls.VOWEL_SOUND_WORDS:
            return True
            
        # Check first letter
        return next_word[0] in cls.VOWEL_SOUNDS
    
    @classmethod
    def get_article_id(cls, next_word: str) -> str:
        """Get the correct article audio ID"""
        if cls.needs_an_article(next_word):
            return 'callflow:1191'  # "This is an"
        else:
            return 'callflow:1190'  # "This is a"

class VariableDetector:
    """Detects and handles dynamic variables in text"""
    
    VARIABLE_PATTERNS = {
        'location': [
            r'\(level\s*\d+\)', r'\(.*location.*\)', r'\(.*building.*\)',
            r'level\s*\d+', r'north\s+\w+', r'south\s+\w+', r'east\s+\w+', r'west\s+\w+'
        ],
        'employee': [
            r'\(employee\)', r'\(.*name.*\)', r'\(contact.*\)',
            r'employee', r'worker', r'technician'
        ],
        'callout_type': [
            r'\(.*callout.*\)', r'electric', r'emergency', r'normal', r'urgent'
        ],
        'reason': [
            r'\(.*reason.*\)', r'\(callout reason\)', r'outage', r'maintenance'
        ],
        'company': [
            r'\(company\)', r'aep', r'dpl', r'weceg', r'integrys'
        ]
    }
    
    @classmethod
    def detect_variables(cls, text: str) -> List[Tuple[str, str, int, int]]:
        """Detect variables in text and return (var_type, matched_text, start, end)"""
        variables = []
        text_lower = text.lower()
        
        for var_type, patterns in cls.VARIABLE_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    variables.append((var_type, match.group(), match.start(), match.end()))
        
        # Sort by position to handle overlaps
        variables.sort(key=lambda x: (x[2], -x[3]))
        
        # Remove overlaps (keep longest match)
        filtered_vars = []
        last_end = -1
        for var in variables:
            if var[2] >= last_end:
                filtered_vars.append(var)
                last_end = var[3]
        
        return filtered_vars

class AudioDatabase:
    """Manages the audio file database and searching"""
    
    def __init__(self, csv_file_path: str):
        self.df = pd.read_csv(csv_file_path)
        self.df['Transcript'] = self.df['Transcript'].astype(str).str.strip()
        self.df['search_text'] = self.df['Transcript'].str.lower()
        
        # Create search indices
        self._build_search_indices()
        logger.info(f"Loaded {len(self.df)} audio files from database")
    
    def _build_search_indices(self):
        """Build search indices for faster lookup"""
        self.exact_match_index = {}
        self.word_index = {}
        
        for idx, row in self.df.iterrows():
            text = row['search_text']
            company = row['Company']
            folder = row['Folder']
            file_name = row['File Name']
            
            # Exact match index
            key = f"{company}_{folder}_{text}"
            if key not in self.exact_match_index:
                self.exact_match_index[key] = []
            self.exact_match_index[key].append({
                'index': idx,
                'company': company,
                'folder': folder,
                'file_name': file_name,
                'transcript': row['Transcript']
            })
            
            # Word-based index for partial matching
            words = text.split()
            for word in words:
                if word not in self.word_index:
                    self.word_index[word] = []
                self.word_index[word].append(idx)
    
    def find_exact_match(self, text: str, company: str = None, folder: str = None) -> List[Dict]:
        """Find exact matches for text"""
        text_lower = text.lower().strip()
        matches = []
        
        if company and folder:
            key = f"{company}_{folder}_{text_lower}"
            matches.extend(self.exact_match_index.get(key, []))
        elif company:
            # Search within company
            for key, entries in self.exact_match_index.items():
                if key.startswith(f"{company}_") and key.endswith(f"_{text_lower}"):
                    matches.extend(entries)
        else:
            # Search all companies
            for key, entries in self.exact_match_index.items():
                if key.endswith(f"_{text_lower}"):
                    matches.extend(entries)
        
        return matches
    
    def find_partial_matches(self, text: str, company: str = None, min_words: int = 2) -> List[Dict]:
        """Find partial matches based on word overlap"""
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        if len(words) < min_words:
            return []
        
        # Find rows that contain multiple words from the search text
        candidate_indices = set()
        for word in words:
            if word in self.word_index:
                candidate_indices.update(self.word_index[word])
        
        matches = []
        for idx in candidate_indices:
            row = self.df.iloc[idx]
            if company and row['Company'] != company:
                continue
                
            # Calculate word overlap
            row_words = set(row['search_text'].split())
            search_words = set(words)
            overlap = len(row_words.intersection(search_words))
            
            if overlap >= min_words:
                similarity = overlap / max(len(row_words), len(search_words))
                matches.append({
                    'index': idx,
                    'company': row['Company'],
                    'folder': row['Folder'],
                    'file_name': row['File Name'],
                    'transcript': row['Transcript'],
                    'similarity': similarity,
                    'word_overlap': overlap
                })
        
        # Sort by similarity
        matches.sort(key=lambda x: (x['similarity'], x['word_overlap']), reverse=True)
        return matches[:10]  # Return top 10 matches

class SegmentAnalyzer:
    """Main class for analyzing text segments and mapping to audio IDs"""
    
    def __init__(self, csv_file_path: str):
        self.audio_db = AudioDatabase(csv_file_path)
        self.grammar_rules = GrammarRules()
        self.variable_detector = VariableDetector()
        
        # Common phrase patterns for segmentation
        self.segment_patterns = [
            r'this is an? ',
            r'press \d+',
            r'if you ',
            r'to the phone',
            r'call.*system',
            r'from \w+',
            r'callout',
            r'thank you',
            r'goodbye',
            r'please',
            r'invalid entry',
            r'try again'
        ]
    
    def analyze_text(self, text: str, company: str = None) -> MappingResult:
        """Analyze text and map to audio file IDs"""
        logger.info(f"Analyzing text: '{text}' for company: {company}")
        
        # Clean and normalize text
        normalized_text = self._normalize_text(text)
        
        # Detect variables first
        variables = self.variable_detector.detect_variables(normalized_text)
        
        # Split text into segments around variables and common phrases
        segments = self._segment_text(normalized_text, variables)
        
        # Map each segment to audio IDs
        mapped_segments = []
        missing_segments = []
        total_confidence = 0
        
        for segment in segments:
            if segment['is_variable']:
                # Handle variable segments
                audio_segment = AudioSegment(
                    text=segment['text'],
                    file_id=f"{segment['var_type']}:{{{{ {segment['var_type']} }}}}",
                    company=company or 'dynamic',
                    folder=segment['var_type'],
                    confidence=1.0,
                    is_variable=True,
                    variable_type=segment['var_type']
                )
                mapped_segments.append(audio_segment)
                total_confidence += 1.0
            else:
                # Handle static text segments
                result = self._map_text_segment(segment['text'], company)
                if result:
                    mapped_segments.append(result)
                    total_confidence += result.confidence
                else:
                    missing_segments.append(segment['text'])
        
        # Calculate overall confidence
        avg_confidence = total_confidence / len(segments) if segments else 0
        requires_review = len(missing_segments) > 0 or avg_confidence < 0.8
        
        return MappingResult(
            original_text=text,
            segments=mapped_segments,
            missing_segments=missing_segments,
            confidence_score=avg_confidence,
            requires_manual_review=requires_review
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for processing"""
        # Remove HTML line breaks
        text = re.sub(r'<br\s*/?>', ' ', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove parentheses content but preserve the parentheses
        # This is handled by variable detection
        return text.strip()
    
    def _segment_text(self, text: str, variables: List[Tuple]) -> List[Dict]:
        """Split text into segments for mapping"""
        segments = []
        last_end = 0
        
        # Sort variables by position
        variables.sort(key=lambda x: x[2])
        
        for var_type, var_text, start, end in variables:
            # Add text before variable
            if start > last_end:
                before_text = text[last_end:start].strip()
                if before_text:
                    segments.extend(self._split_text_segment(before_text))
            
            # Add variable segment
            segments.append({
                'text': var_text,
                'is_variable': True,
                'var_type': var_type
            })
            
            last_end = end
        
        # Add remaining text
        if last_end < len(text):
            remaining_text = text[last_end:].strip()
            if remaining_text:
                segments.extend(self._split_text_segment(remaining_text))
        
        # If no variables found, split the entire text
        if not variables:
            segments.extend(self._split_text_segment(text))
        
        return segments
    
    def _split_text_segment(self, text: str) -> List[Dict]:
        """Split text segment into smaller chunks based on common patterns"""
        segments = []
        remaining = text.strip()
        
        # Try to split on common phrase boundaries
        for pattern in self.segment_patterns:
            if re.search(pattern, remaining, re.IGNORECASE):
                parts = re.split(f'({pattern})', remaining, flags=re.IGNORECASE)
                segments = []
                for part in parts:
                    part = part.strip()
                    if part:
                        segments.append({
                            'text': part,
                            'is_variable': False
                        })
                return segments
        
        # If no patterns match, treat as single segment
        if remaining:
            segments.append({
                'text': remaining,
                'is_variable': False
            })
        
        return segments
    
    def _map_text_segment(self, text: str, company: str = None) -> Optional[AudioSegment]:
        """Map a single text segment to audio file ID"""
        # Try exact match first
        exact_matches = self.audio_db.find_exact_match(text, company)
        
        if exact_matches:
            best_match = self._select_best_match(exact_matches, company)
            file_id = self._generate_file_id(best_match)
            
            return AudioSegment(
                text=text,
                file_id=file_id,
                company=best_match['company'],
                folder=best_match['folder'],
                confidence=1.0
            )
        
        # Try partial matches (but with high standards)
        partial_matches = self.audio_db.find_partial_matches(text, company, min_words=2)
        
        if partial_matches and partial_matches[0]['similarity'] >= 0.9:
            best_match = partial_matches[0]
            file_id = self._generate_file_id(best_match)
            
            return AudioSegment(
                text=text,
                file_id=file_id,
                company=best_match['company'],
                folder=best_match['folder'],
                confidence=best_match['similarity']
            )
        
        return None
    
    def _select_best_match(self, matches: List[Dict], preferred_company: str = None) -> Dict:
        """Select the best match from multiple options"""
        if preferred_company:
            # Prefer matches from the same company
            company_matches = [m for m in matches if m['company'] == preferred_company]
            if company_matches:
                return company_matches[0]
        
        # Return first match (they're all exact anyway)
        return matches[0]
    
    def _generate_file_id(self, match: Dict) -> str:
        """Generate audio file ID from match"""
        folder = match['folder']
        file_name = match['file_name']
        
        # Extract numeric ID from filename (e.g., "1001.ulaw" -> "1001")
        numeric_id = re.search(r'(\d+)', file_name)
        if numeric_id:
            id_num = numeric_id.group(1)
            return f"{folder}:{id_num}"
        
        # Fallback to filename without extension
        base_name = file_name.split('.')[0]
        return f"{folder}:{base_name}"
    
    def generate_ivr_prompt_array(self, mapping_result: MappingResult) -> List[str]:
        """Generate IVR playPrompt array from mapping result"""
        prompt_array = []
        
        for segment in mapping_result.segments:
            if segment.is_variable:
                prompt_array.append(segment.file_id)
            else:
                prompt_array.append(segment.file_id)
        
        return prompt_array
    
    def get_mapping_report(self, mapping_result: MappingResult) -> Dict:
        """Generate detailed report of mapping results"""
        return {
            'original_text': mapping_result.original_text,
            'total_segments': len(mapping_result.segments),
            'mapped_segments': len([s for s in mapping_result.segments if not s.is_variable]),
            'variable_segments': len([s for s in mapping_result.segments if s.is_variable]),
            'missing_segments': len(mapping_result.missing_segments),
            'confidence_score': mapping_result.confidence_score,
            'requires_manual_review': mapping_result.requires_manual_review,
            'segments_detail': [
                {
                    'text': seg.text,
                    'file_id': seg.file_id,
                    'company': seg.company,
                    'folder': seg.folder,
                    'confidence': seg.confidence,
                    'is_variable': seg.is_variable
                }
                for seg in mapping_result.segments
            ],
            'missing_segments_detail': mapping_result.missing_segments,
            'ivr_prompt_array': self.generate_ivr_prompt_array(mapping_result)
        }

# Usage example and testing functions
def test_segment_analyzer():
    """Test the segment analyzer with sample data"""
    # This would use your actual CSV file
    # analyzer = SegmentAnalyzer('cf_general_structure.csv')
    
    # Sample test cases
    test_cases = [
        "This is an electric callout from Level 2",
        "Press 1 if this is (employee)",
        "Press 3 if you need more time",
        "Thank you. Goodbye.",
        "Invalid entry. Please try again."
    ]
    
    print("Testing Segment Analyzer")
    print("=" * 50)
    
    for test_text in test_cases:
        print(f"\nAnalyzing: '{test_text}'")
        print("-" * 30)
        
        # Would analyze with actual data
        # result = analyzer.analyze_text(test_text, company='dpl')
        # report = analyzer.get_mapping_report(result)
        # print(json.dumps(report, indent=2))

if __name__ == "__main__":
    test_segment_analyzer()