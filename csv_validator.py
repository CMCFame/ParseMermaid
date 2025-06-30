"""
CSV Database Validator and Analyzer
Validates and analyzes your audio transcription database for optimal IVR mapping
"""

import pandas as pd
import re
import json
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVDatabaseValidator:
    """Validates and analyzes the audio transcription database"""
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.df = None
        self.validation_results = {}
        self.analysis_results = {}
        
    def load_and_validate(self) -> Dict:
        """Load CSV and perform comprehensive validation"""
        try:
            # Load CSV
            self.df = pd.read_csv(self.csv_file_path)
            logger.info(f"✅ Loaded CSV with {len(self.df)} records")
            
            # Run all validation checks
            self.validation_results = {
                'file_structure': self._validate_file_structure(),
                'data_quality': self._validate_data_quality(),
                'content_analysis': self._analyze_content(),
                'company_coverage': self._analyze_company_coverage(),
                'folder_structure': self._analyze_folder_structure(),
                'transcript_quality': self._analyze_transcript_quality(),
                'missing_segments': self._identify_missing_common_segments(),
                'recommendations': self._generate_recommendations()
            }
            
            return self.validation_results
            
        except Exception as e:
            logger.error(f"❌ Failed to load CSV: {str(e)}")
            return {'error': str(e)}
    
    def _validate_file_structure(self) -> Dict:
        """Validate basic file structure"""
        required_columns = ['Company', 'Folder', 'File Name', 'Transcript']
        missing_columns = [col for col in required_columns if col not in self.df.columns]
        
        return {
            'required_columns_present': len(missing_columns) == 0,
            'missing_columns': missing_columns,
            'total_columns': len(self.df.columns),
            'column_names': list(self.df.columns),
            'total_rows': len(self.df)
        }
    
    def _validate_data_quality(self) -> Dict:
        """Validate data quality issues"""
        issues = []
        
        # Check for null values
        null_counts = self.df.isnull().sum()
        for col, count in null_counts.items():
            if count > 0:
                issues.append(f"{count} null values in {col}")
        
        # Check for empty transcripts
        empty_transcripts = self.df['Transcript'].astype(str).str.strip() == ''
        empty_count = empty_transcripts.sum()
        if empty_count > 0:
            issues.append(f"{empty_count} empty transcripts")
        
        # Check for duplicate file names within same company/folder
        duplicates = self.df.groupby(['Company', 'Folder', 'File Name']).size()
        duplicate_count = (duplicates > 1).sum()
        if duplicate_count > 0:
            issues.append(f"{duplicate_count} duplicate file names")
        
        # Check file name format
        invalid_filenames = []
        for idx, row in self.df.iterrows():
            filename = str(row['File Name'])
            if not re.match(r'^\d+\.(ulaw|wav|mp3)$', filename):
                invalid_filenames.append(filename)
        
        if invalid_filenames:
            issues.append(f"{len(invalid_filenames)} invalid file name formats")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues,
            'null_value_summary': null_counts.to_dict(),
            'duplicate_files': duplicate_count,
            'invalid_filenames': invalid_filenames[:10]  # Show first 10
        }
    
    def _analyze_content(self) -> Dict:
        """Analyze content distribution and patterns"""
        # Transcript length analysis
        transcript_lengths = self.df['Transcript'].astype(str).str.len()
        
        # Common words analysis
        all_text = ' '.join(self.df['Transcript'].astype(str).str.lower())
        words = re.findall(r'\b\w+\b', all_text)
        word_counts = Counter(words)
        
        # Phrase patterns
        common_phrases = self._extract_common_phrases()
        
        return {
            'transcript_length_stats': {
                'min': int(transcript_lengths.min()),
                'max': int(transcript_lengths.max()),
                'mean': round(transcript_lengths.mean(), 1),
                'median': int(transcript_lengths.median())
            },
            'most_common_words': word_counts.most_common(20),
            'common_phrases': common_phrases,
            'total_unique_transcripts': len(self.df['Transcript'].unique())
        }
    
    def _analyze_company_coverage(self) -> Dict:
        """Analyze company and context coverage"""
        company_stats = {}
        
        for company in self.df['Company'].unique():
            company_data = self.df[self.df['Company'] == company]
            folders = company_data['Folder'].unique()
            
            company_stats[company] = {
                'total_files': len(company_data),
                'folders': list(folders),
                'folder_counts': company_data['Folder'].value_counts().to_dict()
            }
        
        return {
            'total_companies': len(self.df['Company'].unique()),
            'companies': list(self.df['Company'].unique()),
            'company_distribution': self.df['Company'].value_counts().to_dict(),
            'company_details': company_stats
        }
    
    def _analyze_folder_structure(self) -> Dict:
        """Analyze folder structure and categorization"""
        folder_analysis = {}
        
        # Expected folder types based on project knowledge
        expected_folders = {
            'callout_type': 'Types of calls (Normal, Emergency, etc.)',
            'company': 'Company name recordings',
            'location': 'Location names',
            'job_classification': 'Job titles',
            'custom_message': 'Special messages',
            'new_std_speech': 'Standard phrases',
            'callflow': 'General call flow segments'
        }
        
        for folder in self.df['Folder'].unique():
            folder_data = self.df[self.df['Folder'] == folder]
            folder_analysis[folder] = {
                'file_count': len(folder_data),
                'companies': list(folder_data['Company'].unique()),
                'is_expected': folder in expected_folders,
                'description': expected_folders.get(folder, 'Unknown folder type'),
                'sample_transcripts': folder_data['Transcript'].head(5).tolist()
            }
        
        missing_folders = [f for f in expected_folders if f not in self.df['Folder'].unique()]
        
        return {
            'total_folders': len(self.df['Folder'].unique()),
            'folder_distribution': self.df['Folder'].value_counts().to_dict(),
            'folder_analysis': folder_analysis,
            'missing_expected_folders': missing_folders,
            'unexpected_folders': [f for f in self.df['Folder'].unique() if f not in expected_folders]
        }
    
    def _analyze_transcript_quality(self) -> Dict:
        """Analyze transcript text quality for mapping"""
        quality_issues = []
        
        # Check for common transcription issues
        transcripts = self.df['Transcript'].astype(str)
        
        # Very short transcripts (likely incomplete)
        very_short = transcripts.str.len() < 3
        if very_short.any():
            quality_issues.append(f"{very_short.sum()} very short transcripts (< 3 chars)")
        
        # Transcripts with numbers only
        numbers_only = transcripts.str.match(r'^\d+\.?$')
        if numbers_only.any():
            quality_issues.append(f"{numbers_only.sum()} transcripts with numbers only")
        
        # Transcripts with special characters that might cause issues
        special_chars = transcripts.str.contains(r'[^\w\s\.\,\!\?\-\(\)]')
        if special_chars.any():
            quality_issues.append(f"{special_chars.sum()} transcripts with special characters")
        
        # Check for potential grammar rule cases
        grammar_cases = self._identify_grammar_cases()
        
        return {
            'quality_issues': quality_issues,
            'grammar_analysis': grammar_cases,
            'encoding_check': self._check_text_encoding()
        }
    
    def _identify_grammar_cases(self) -> Dict:
        """Identify cases where grammar rules apply"""
        transcripts = self.df['Transcript'].astype(str).str.lower()
        
        # Find "this is" patterns
        this_is_a = transcripts.str.contains(r'\bthis is a\b').sum()
        this_is_an = transcripts.str.contains(r'\bthis is an\b').sum()
        
        # Find words that typically need "an"
        vowel_words = []
        for transcript in transcripts:
            words = transcript.split()
            for word in words:
                if word and word[0] in 'aeiou':
                    vowel_words.append(word)
        
        vowel_word_counts = Counter(vowel_words)
        
        return {
            'this_is_a_count': this_is_a,
            'this_is_an_count': this_is_an,
            'common_vowel_words': vowel_word_counts.most_common(10),
            'grammar_rule_applicable': this_is_a > 0 or this_is_an > 0
        }
    
    def _check_text_encoding(self) -> Dict:
        """Check for text encoding issues"""
        encoding_issues = []
        
        transcripts = self.df['Transcript'].astype(str)
        
        # Check for non-ASCII characters
        non_ascii = transcripts.str.contains(r'[^\x00-\x7F]')
        if non_ascii.any():
            encoding_issues.append(f"{non_ascii.sum()} transcripts with non-ASCII characters")
        
        # Check for common encoding artifacts
        artifacts = [r'Ã', r'â€', r'Â', r'Ã¡', r'Ã©']
        for artifact in artifacts:
            matches = transcripts.str.contains(artifact)
            if matches.any():
                encoding_issues.append(f"{matches.sum()} transcripts with '{artifact}' artifacts")
        
        return {
            'has_encoding_issues': len(encoding_issues) > 0,
            'issues': encoding_issues
        }
    
    def _extract_common_phrases(self) -> List[Tuple[str, int]]:
        """Extract common phrases that could be useful for mapping"""
        all_text = ' '.join(self.df['Transcript'].astype(str).str.lower())
        
        # Common IVR phrases to look for
        ivr_patterns = [
            r'\bpress \d+\b',
            r'\bthis is an?\b',
            r'\bcallout\b',
            r'\binvalid entry\b',
            r'\btry again\b',
            r'\bthank you\b',
            r'\bgoodbye\b',
            r'\benter .*pin\b',
            r'\bnot home\b',
            r'\bavailable\b'
        ]
        
        phrase_counts = []
        for pattern in ivr_patterns:
            matches = re.findall(pattern, all_text)
            if matches:
                phrase_counts.append((pattern, len(matches)))
        
        return sorted(phrase_counts, key=lambda x: x[1], reverse=True)
    
    def _identify_missing_common_segments(self) -> Dict:
        """Identify commonly needed segments that might be missing"""
        transcripts_lower = set(self.df['Transcript'].astype(str).str.lower())
        
        # Common segments needed for IVR flows
        expected_segments = {
            'articles': ['this is a', 'this is an'],
            'actions': ['press 1', 'press 3', 'press 7', 'press 9'],
            'responses': ['invalid entry', 'please try again', 'thank you', 'goodbye'],
            'callout_terms': ['callout', 'electric', 'emergency', 'normal'],
            'locations': ['level 1', 'level 2', 'north', 'south', 'east', 'west'],
            'prompts': ['enter your pin', 'are you available', 'not home']
        }
        
        missing_by_category = {}
        for category, segments in expected_segments.items():
            missing = [seg for seg in segments if seg not in transcripts_lower]
            if missing:
                missing_by_category[category] = missing
        
        return {
            'missing_segments_by_category': missing_by_category,
            'total_missing_segments': sum(len(segs) for segs in missing_by_category.values())
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations for improving the database"""
        recommendations = []
        
        # Data quality recommendations
        if self.validation_results.get('data_quality', {}).get('has_issues'):
            recommendations.append("🔧 Fix data quality issues: Clean null values and duplicates")
        
        # Missing folder recommendations
        missing_folders = self.validation_results.get('folder_structure', {}).get('missing_expected_folders', [])
        if missing_folders:
            recommendations.append(f"📁 Add missing folder types: {', '.join(missing_folders)}")
        
        # Grammar rule recommendations
        grammar = self.validation_results.get('transcript_quality', {}).get('grammar_analysis', {})
        if grammar.get('grammar_rule_applicable'):
            recommendations.append("📝 Verify 'a/an' grammar consistency for article detection")
        
        # Coverage recommendations
        companies = self.validation_results.get('company_coverage', {}).get('total_companies', 0)
        if companies < 2:
            recommendations.append("🏢 Add more company contexts for better mapping flexibility")
        
        # Missing segments recommendations
        missing_count = self.validation_results.get('missing_segments', {}).get('total_missing_segments', 0)
        if missing_count > 0:
            recommendations.append(f"🎤 Record {missing_count} missing common segments for better coverage")
        
        # Performance recommendations
        if len(self.df) > 10000:
            recommendations.append("⚡ Consider database indexing for performance with large datasets")
        
        return recommendations
    
    def generate_report(self) -> str:
        """Generate a comprehensive validation report"""
        if not self.validation_results:
            return "❌ No validation results available. Run load_and_validate() first."
        
        report = []
        report.append("="*80)
        report.append("🔍 CSV DATABASE VALIDATION REPORT")
        report.append("="*80)
        
        # File structure
        structure = self.validation_results['file_structure']
        report.append(f"\n📁 FILE STRUCTURE")
        report.append(f"   ✅ Total rows: {structure['total_rows']:,}")
        report.append(f"   ✅ Total columns: {structure['total_columns']}")
        if structure['required_columns_present']:
            report.append("   ✅ All required columns present")
        else:
            report.append(f"   ❌ Missing columns: {', '.join(structure['missing_columns'])}")
        
        # Data quality
        quality = self.validation_results['data_quality']
        report.append(f"\n🔍 DATA QUALITY")
        if quality['has_issues']:
            report.append("   ⚠️ Issues found:")
            for issue in quality['issues']:
                report.append(f"      • {issue}")
        else:
            report.append("   ✅ No data quality issues detected")
        
        # Company coverage
        coverage = self.validation_results['company_coverage']
        report.append(f"\n🏢 COMPANY COVERAGE")
        report.append(f"   📊 Total companies: {coverage['total_companies']}")
        for company, count in coverage['company_distribution'].items():
            report.append(f"      • {company}: {count:,} files")
        
        # Folder structure
        folders = self.validation_results['folder_structure']
        report.append(f"\n📂 FOLDER STRUCTURE")
        report.append(f"   📊 Total folders: {folders['total_folders']}")
        if folders['missing_expected_folders']:
            report.append(f"   ⚠️ Missing expected folders: {', '.join(folders['missing_expected_folders'])}")
        if folders['unexpected_folders']:
            report.append(f"   ℹ️ Unexpected folders: {', '.join(folders['unexpected_folders'])}")
        
        # Missing segments
        missing = self.validation_results['missing_segments']
        if missing['total_missing_segments'] > 0:
            report.append(f"\n🎤 MISSING SEGMENTS")
            report.append(f"   ⚠️ Total missing common segments: {missing['total_missing_segments']}")
            for category, segments in missing['missing_segments_by_category'].items():
                report.append(f"      • {category}: {', '.join(segments)}")
        
        # Recommendations
        recommendations = self.validation_results['recommendations']
        if recommendations:
            report.append(f"\n💡 RECOMMENDATIONS")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"   {i}. {rec}")
        
        # Overall assessment
        report.append(f"\n🎯 OVERALL ASSESSMENT")
        total_issues = len(quality.get('issues', [])) + len(missing.get('missing_segments_by_category', {}))
        if total_issues == 0:
            report.append("   ✅ Database is ready for production use!")
        elif total_issues < 5:
            report.append("   ⚠️ Database needs minor improvements before production")
        else:
            report.append("   ❌ Database needs significant improvements before production")
        
        report.append("="*80)
        
        return "\n".join(report)
    
    def export_analysis(self, output_file: str = "database_analysis.json"):
        """Export detailed analysis to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        logger.info(f"✅ Analysis exported to {output_file}")

# Utility functions for testing and validation
def quick_validate_csv(csv_file_path: str) -> bool:
    """Quick validation check for CSV file"""
    try:
        validator = CSVDatabaseValidator(csv_file_path)
        results = validator.load_and_validate()
        
        # Check critical issues
        if 'error' in results:
            print(f"❌ Cannot load CSV: {results['error']}")
            return False
        
        structure_ok = results['file_structure']['required_columns_present']
        no_critical_issues = not results['data_quality']['has_issues']
        
        if structure_ok and no_critical_issues:
            print("✅ CSV validation passed")
            return True
        else:
            print("⚠️ CSV has issues - run full validation for details")
            return False
            
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        return False

def analyze_csv_for_mapping(csv_file_path: str):
    """Analyze CSV specifically for IVR mapping readiness"""
    validator = CSVDatabaseValidator(csv_file_path)
    results = validator.load_and_validate()
    
    if 'error' in results:
        print(f"❌ Error: {results['error']}")
        return
    
    print(validator.generate_report())
    
    # Export detailed analysis
    validator.export_analysis()
    
    return results

# Main execution
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "cf_general_structure.csv"
    
    print(f"🔍 Analyzing CSV database: {csv_file}")
    print("="*60)
    
    # Run comprehensive analysis
    try:
        results = analyze_csv_for_mapping(csv_file)
        print(f"\n✅ Analysis complete! Check 'database_analysis.json' for detailed results.")
    except FileNotFoundError:
        print(f"❌ File not found: {csv_file}")
        print("💡 Make sure the CSV file path is correct")
    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")