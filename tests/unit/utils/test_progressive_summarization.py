"""Tests for progressive summarization functionality."""

# pylint: disable=too-many-lines

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.llm.summarization.progressive import (
    ChunkSummary,
    PassSummaryOutput,
    ProgressiveSummaryResult,
    SummarizationStrategy,
    SummaryPass,
    calculate_reduction_targets,
    perform_summary_pass,
    progressive_summarize,
    summarize_chunk,
    summarize_with_chunking,
)


@pytest.mark.unit
class TestCalculateReductionTargets:
    """Test reduction target calculation."""

    def test_aggressive_strategy(self):
        """Test aggressive reduction targets."""
        targets = calculate_reduction_targets(
            original_tokens=10000,
            target_tokens=1000,
            max_passes=3,
            strategy=SummarizationStrategy.AGGRESSIVE,
        )

        assert len(targets) == 3
        assert targets[0] == 5000  # 50% of 10000
        assert targets[1] == 1500  # 30% of 5000
        assert targets[2] == 1000  # Target reached

    def test_balanced_strategy(self):
        """Test balanced reduction targets."""
        targets = calculate_reduction_targets(
            original_tokens=10000,
            target_tokens=1000,
            max_passes=3,
            strategy=SummarizationStrategy.BALANCED,
        )

        assert len(targets) == 3
        assert targets[0] == 6000  # 60% of 10000
        assert targets[1] == 2400  # 40% of 6000
        assert targets[2] == 1000  # Target reached

    def test_conservative_strategy(self):
        """Test conservative reduction targets."""
        targets = calculate_reduction_targets(
            original_tokens=10000,
            target_tokens=1000,
            max_passes=3,
            strategy=SummarizationStrategy.CONSERVATIVE,
        )

        assert len(targets) == 3
        assert targets[0] == 7000  # 70% of 10000
        assert targets[1] == 3500  # 50% of 7000
        assert targets[2] == 1225  # 35% of 3500


@pytest.mark.unit
class TestPerformSummaryPass:
    """Test individual summary pass."""

    @pytest.mark.asyncio
    async def test_successful_pass(self):
        """Test successful summarization pass."""
        mock_llm = MagicMock()

        # Mock token counting
        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = [5000, 2000]  # input, output

            # Mock LLMTextCompletionProgram
            with patch(
                "src.shared.llm.summarization.progressive.LLMTextCompletionProgram"
            ) as mock_program_class:
                mock_program = MagicMock()
                mock_program_class.from_defaults.return_value = mock_program

                # Mock program output
                mock_result = PassSummaryOutput(
                    summary="Summarized content here",
                    key_points=["Point 1", "Point 2"],
                    topics=["Topic A", "Topic B"],
                )
                mock_program.acall = AsyncMock(return_value=mock_result)

                result = await perform_summary_pass(
                    text="Original long text",
                    llm=mock_llm,
                    pass_number=1,
                    target_tokens=2000,
                )

                assert isinstance(result, SummaryPass)
                assert result.pass_number == 1
                assert result.input_tokens == 5000
                assert result.output_tokens == 2000
                assert result.reduction_ratio == 0.6  # (5000-2000)/5000
                assert result.summary == "Summarized content here"
                assert len(result.key_points_retained) == 2
                assert len(result.topics_covered) == 2

    @pytest.mark.asyncio
    async def test_pass_with_fallback(self):
        """Test pass with fallback to truncation."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = [5000, 1800]  # input, truncated output

            # Mock LLMTextCompletionProgram to raise error
            with patch(
                "src.shared.llm.summarization.progressive.LLMTextCompletionProgram"
            ) as mock_program_class:
                mock_program_class.from_defaults.side_effect = Exception("LLM error")

                # Mock truncation
                with patch(
                    "src.shared.llm.summarization.progressive."
                    "truncate_text_by_tokens"
                ) as mock_truncate:
                    mock_truncate.return_value = "Truncated text"

                    result = await perform_summary_pass(
                        text="Original long text",
                        llm=mock_llm,
                        pass_number=1,
                        target_tokens=2000,
                    )

                    assert isinstance(result, SummaryPass)
                    assert result.summary == "Truncated text"
                    mock_truncate.assert_called_once()


@pytest.mark.unit
class TestProgressiveSummarize:
    """Test complete progressive summarization."""

    @pytest.mark.asyncio
    async def test_no_summarization_needed(self):
        """Test when text is already within target."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.return_value = 1000  # Already below target

            result = await progressive_summarize(
                text="Short text",
                llm=mock_llm,
                target_tokens=2000,
            )

            assert isinstance(result, ProgressiveSummaryResult)
            assert result.total_passes == 0
            assert result.final_summary == "Short text"
            assert result.overall_reduction == 0.0
            assert len(result.warnings) == 1

    @pytest.mark.asyncio
    async def test_multi_pass_summarization(self):
        """Test multi-pass summarization."""
        mock_llm = MagicMock()

        # Mock token counts for progressive reduction
        token_counts = [10000, 6000, 2400, 1000]  # Original, pass1, pass2, pass3
        count_idx = [0]

        def mock_count_tokens(*args, **kwargs):
            result = token_counts[count_idx[0]]
            count_idx[0] = min(count_idx[0] + 1, len(token_counts) - 1)
            return result

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = mock_count_tokens

            # Mock get_max_context_tokens to prevent chunking
            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                mock_max_context.return_value = (
                    128000  # Large enough to not trigger chunking
                )

                # Mock perform_summary_pass
                with patch(
                    "src.shared.llm.summarization.progressive.perform_summary_pass"
                ) as mock_perform:

                    async def mock_pass(text, llm, pass_number, target_tokens):
                        return SummaryPass(
                            pass_number=pass_number,
                            input_tokens=token_counts[pass_number - 1],
                            output_tokens=token_counts[pass_number],
                            reduction_ratio=0.4,
                            summary=f"Summary from pass {pass_number}",
                            key_points_retained=[],
                            topics_covered=[],
                        )

                    mock_perform.side_effect = mock_pass

                    result = await progressive_summarize(
                        text="Very long original text",
                        llm=mock_llm,
                        target_tokens=1500,
                        max_passes=3,
                        strategy=SummarizationStrategy.BALANCED,
                    )

                    assert isinstance(result, ProgressiveSummaryResult)
                    # Should exit after 2 passes since 1000 < 1500 target
                    assert result.total_passes == 2
                    assert result.original_tokens == 10000
                    assert result.final_tokens == 1000
                    assert result.overall_reduction == 0.9
                    assert len(result.passes) == 2

    @pytest.mark.asyncio
    async def test_early_exit_when_target_reached(self):
        """Test early exit when target is reached before max passes."""
        mock_llm = MagicMock()

        # Token counts: original, after pass1, check after pass1
        token_counts = [10000, 3000, 800]
        count_idx = [0]

        def mock_count_tokens(*args, **kwargs):
            result = token_counts[count_idx[0]]
            count_idx[0] = min(count_idx[0] + 1, len(token_counts) - 1)
            return result

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = mock_count_tokens

            # Mock get_max_context_tokens to prevent chunking
            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                mock_max_context.return_value = (
                    128000  # Large enough to not trigger chunking
                )

                with patch(
                    "src.shared.llm.summarization.progressive.perform_summary_pass"
                ) as mock_perform:

                    async def mock_pass(text, llm, pass_number, target_tokens):
                        return SummaryPass(
                            pass_number=pass_number,
                            input_tokens=10000,
                            output_tokens=800,
                            reduction_ratio=0.92,
                            summary="Highly summarized",
                            key_points_retained=[],
                            topics_covered=[],
                        )

                    mock_perform.side_effect = mock_pass

                    result = await progressive_summarize(
                        text="Long text",
                        llm=mock_llm,
                        target_tokens=1000,
                        max_passes=3,
                    )

                    # Should exit after 1 pass since target was reached
                    assert result.total_passes == 1
                    assert result.final_tokens == 800


@pytest.mark.unit
class TestSummarizationStrategy:
    """Test summarization strategy enum."""

    def test_strategy_values(self):
        """Test strategy enum values."""
        assert SummarizationStrategy.AGGRESSIVE.value == "aggressive"
        assert SummarizationStrategy.BALANCED.value == "balanced"
        assert SummarizationStrategy.CONSERVATIVE.value == "conservative"

    def test_strategy_from_string(self):
        """Test creating strategy from config string."""
        strategy_map = {
            "aggressive": SummarizationStrategy.AGGRESSIVE,
            "balanced": SummarizationStrategy.BALANCED,
            "conservative": SummarizationStrategy.CONSERVATIVE,
        }

        assert strategy_map["aggressive"] == SummarizationStrategy.AGGRESSIVE
        assert strategy_map["balanced"] == SummarizationStrategy.BALANCED
        assert strategy_map["conservative"] == SummarizationStrategy.CONSERVATIVE


@pytest.mark.unit
class TestSummarizeChunk:
    """Test chunk summarization."""

    @pytest.mark.asyncio
    async def test_successful_chunk_summarization(self):
        """Test successful summarization of a chunk."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = [5000, 3000]  # input, output

            with patch(
                "src.shared.llm.summarization.progressive.LLMTextCompletionProgram"
            ) as mock_program_class:
                mock_program = MagicMock()
                mock_program_class.from_defaults.return_value = mock_program

                mock_result = PassSummaryOutput(
                    summary="Chunk summary",
                    key_points=["Key point 1"],
                    topics=["Topic 1"],
                )
                mock_program.acall = AsyncMock(return_value=mock_result)

                result = await summarize_chunk(
                    chunk="Chunk text",
                    chunk_number=1,
                    llm=mock_llm,
                    target_reduction=0.6,
                )

                assert isinstance(result, ChunkSummary)
                assert result.chunk_number == 1
                assert result.input_tokens == 5000
                assert result.output_tokens == 3000
                assert result.summary == "Chunk summary"
                assert len(result.key_points) == 1

    @pytest.mark.asyncio
    async def test_chunk_summarization_with_fallback(self):
        """Test chunk summarization with fallback to truncation."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = [5000, 2800]

            with patch(
                "src.shared.llm.summarization.progressive.LLMTextCompletionProgram"
            ) as mock_program_class:
                mock_program_class.from_defaults.side_effect = Exception("LLM error")

                with patch(
                    "src.shared.llm.summarization.progressive."
                    "truncate_text_by_tokens"
                ) as mock_truncate:
                    mock_truncate.return_value = "Truncated chunk"

                    result = await summarize_chunk(
                        chunk="Chunk text",
                        chunk_number=2,
                        llm=mock_llm,
                    )

                    assert result.summary == "Truncated chunk"
                    assert result.chunk_number == 2
                    mock_truncate.assert_called_once()


@pytest.mark.unit
class TestSummarizeWithChunking:
    """Test chunking-based summarization."""

    @pytest.mark.asyncio
    async def test_chunking_summarization(self):
        """Test summarization with chunking."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            # Original: 100k, combined chunks: 15k
            mock_count.side_effect = [100000, 15000]

            with patch(
                "src.shared.llm.summarization.progressive.chunk_text_by_tokens"
            ) as mock_chunk:
                # Simulate 3 chunks
                mock_chunk.return_value = ["chunk1", "chunk2", "chunk3"]

                with patch(
                    "src.shared.llm.summarization.progressive.summarize_chunk"
                ) as mock_summarize_chunk:

                    async def mock_chunk_summary(chunk, chunk_number, llm, **kwargs):
                        return ChunkSummary(
                            chunk_number=chunk_number,
                            input_tokens=33000,
                            output_tokens=5000,
                            summary=f"Summary of chunk {chunk_number}",
                            key_points=[f"Point from chunk {chunk_number}"],
                        )

                    mock_summarize_chunk.side_effect = mock_chunk_summary

                    combined, summaries, warnings = await summarize_with_chunking(
                        text="Very long text",
                        llm=mock_llm,
                        target_tokens=10000,
                        chunk_size=40000,
                        chunk_overlap=500,
                    )

                    assert len(summaries) == 3
                    assert "Section 1" in combined
                    assert "Section 2" in combined
                    assert "Section 3" in combined
                    # Combined (15k) exceeds target (10k), should have warning
                    assert len(warnings) == 1

    @pytest.mark.asyncio
    async def test_chunking_within_target(self):
        """Test chunking where combined result is within target."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            # Original: 100k, combined chunks: 8k (within 10k target)
            mock_count.side_effect = [100000, 8000]

            with patch(
                "src.shared.llm.summarization.progressive.chunk_text_by_tokens"
            ) as mock_chunk:
                mock_chunk.return_value = ["chunk1", "chunk2"]

                with patch(
                    "src.shared.llm.summarization.progressive.summarize_chunk"
                ) as mock_summarize_chunk:

                    async def mock_chunk_summary(chunk, chunk_number, llm, **kwargs):
                        return ChunkSummary(
                            chunk_number=chunk_number,
                            input_tokens=50000,
                            output_tokens=4000,
                            summary=f"Summary {chunk_number}",
                            key_points=[],
                        )

                    mock_summarize_chunk.side_effect = mock_chunk_summary

                    _, summaries, warnings = await summarize_with_chunking(
                        text="Long text",
                        llm=mock_llm,
                        target_tokens=10000,
                        chunk_size=50000,
                        chunk_overlap=500,
                    )

                    assert len(summaries) == 2
                    # No warning since 8k < 10k target
                    assert len(warnings) == 0


@pytest.mark.unit
class TestProgressiveSummarizeWithChunking:
    """Test progressive summarization with chunking integration."""

    @pytest.mark.asyncio
    async def test_chunking_triggered(self):
        """Test that chunking is triggered for very large documents."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            # Original: 100k tokens
            mock_count.return_value = 100000

            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                # Context window: 128k, threshold (50%): 64k
                # 100k > 64k, so chunking should trigger
                mock_max_context.return_value = 128000

                with patch(
                    "src.shared.llm.summarization.progressive."
                    "summarize_with_chunking"
                ) as mock_chunk_summarize:

                    async def mock_chunking(*args, **kwargs):
                        return (
                            "Combined chunk summary",
                            [
                                ChunkSummary(
                                    chunk_number=1,
                                    input_tokens=50000,
                                    output_tokens=30000,
                                    summary="Summary 1",
                                    key_points=[],
                                )
                            ],
                            [],
                        )

                    mock_chunk_summarize.side_effect = mock_chunking

                    # Mock progressive passes (won't be called if
                    # chunking reduces enough)
                    with patch(
                        "src.shared.llm.summarization.progressive."
                        "perform_summary_pass"
                    ) as mock_perform:

                        async def mock_pass(*args, **kwargs):
                            return SummaryPass(
                                pass_number=1,
                                input_tokens=30000,
                                output_tokens=8000,
                                reduction_ratio=0.73,
                                summary="Final summary",
                                key_points_retained=[],
                                topics_covered=[],
                            )

                        mock_perform.side_effect = mock_pass

                        result = await progressive_summarize(
                            text="Extremely long text",
                            llm=mock_llm,
                            target_tokens=10000,
                            chunk_threshold_ratio=0.5,
                            chunk_size_ratio=0.4,
                        )

                        # Verify chunking was triggered
                        mock_chunk_summarize.assert_called_once()
                        assert result.was_chunked is True
                        assert result.num_chunks == 1


@pytest.mark.unit
class TestSummarizeMeetingNotes:
    """Test meeting notes summarization."""

    @pytest.mark.asyncio
    async def test_successful_meeting_notes_summarization(self):
        """Test successful summarization of meeting notes."""
        mock_llm = MagicMock()
        meeting_text = "This is a long meeting with many discussions and decisions."

        with patch(
            "src.shared.llm.summarization.progressive.LLMTextCompletionProgram"
        ) as mock_program_class:
            mock_program = MagicMock()
            mock_program_class.from_defaults.return_value = mock_program

            from src.shared.llm.summarization.progressive import (
                MeetingNotesSummary,
                summarize_meeting_notes,
            )

            mock_result = MeetingNotesSummary(
                summary="Meeting focused on project planning",
                key_decisions=["Decision 1", "Decision 2"],
                topics_discussed=["Planning", "Budget"],
            )
            mock_program.acall = AsyncMock(return_value=mock_result)

            result = await summarize_meeting_notes(
                meeting_notes=meeting_text,
                llm=mock_llm,
                target_length_ratio=0.4,
            )

            assert isinstance(result, str)
            assert "Meeting Summary" in result
            assert "Key Decisions" in result
            assert "Topics Discussed" in result
            assert "Decision 1" in result
            assert "Planning" in result

    @pytest.mark.asyncio
    async def test_meeting_notes_with_fallback(self):
        """Test meeting notes summarization with fallback."""
        mock_llm = MagicMock()
        meeting_text = "Meeting notes that will fail to summarize."

        with patch(
            "src.shared.llm.summarization.progressive.LLMTextCompletionProgram"
        ) as mock_program_class:
            mock_program_class.from_defaults.side_effect = Exception("LLM error")

            with patch(
                "src.shared.llm.summarization.progressive.truncate_text_by_tokens"
            ) as mock_truncate:
                mock_truncate.return_value = "Truncated meeting notes"

                from src.shared.llm.summarization.progressive import (
                    summarize_meeting_notes,
                )

                result = await summarize_meeting_notes(
                    meeting_notes=meeting_text,
                    llm=mock_llm,
                )

                assert result == "Truncated meeting notes"
                mock_truncate.assert_called_once()


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_text_summarization(self):
        """Test progressive summarization with empty text."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.return_value = 0

            result = await progressive_summarize(
                text="",
                llm=mock_llm,
                target_tokens=1000,
            )

            assert isinstance(result, ProgressiveSummaryResult)
            assert result.total_passes == 0
            assert result.final_summary == ""
            assert result.original_tokens == 0
            assert result.final_tokens == 0

    @pytest.mark.asyncio
    async def test_very_small_text(self):
        """Test with text smaller than target."""
        mock_llm = MagicMock()
        small_text = "Just a few words."

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.return_value = 5  # Very small

            result = await progressive_summarize(
                text=small_text,
                llm=mock_llm,
                target_tokens=1000,
            )

            assert result.total_passes == 0
            assert result.final_summary == small_text
            assert len(result.warnings) == 1
            assert "already within target" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_single_pass_sufficient(self):
        """Test when single pass is sufficient to reach target."""
        mock_llm = MagicMock()

        # Original check, before pass 1, after pass 1, check after pass 1
        token_counts = [10000, 10000, 800, 800]
        count_idx = [0]

        def mock_count_tokens(*args, **kwargs):
            result = token_counts[count_idx[0]]
            count_idx[0] = min(count_idx[0] + 1, len(token_counts) - 1)
            return result

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = mock_count_tokens

            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                mock_max_context.return_value = 128000

                with patch(
                    "src.shared.llm.summarization.progressive.perform_summary_pass"
                ) as mock_perform:

                    async def mock_pass(*args, **kwargs):
                        return SummaryPass(
                            pass_number=1,
                            input_tokens=10000,
                            output_tokens=800,
                            reduction_ratio=0.92,
                            summary="Single pass summary",
                            key_points_retained=["Key point"],
                            topics_covered=["Topic"],
                        )

                    mock_perform.side_effect = mock_pass

                    result = await progressive_summarize(
                        text="Text requiring single pass",
                        llm=mock_llm,
                        target_tokens=1000,
                    )

                    # Should stop after 1 pass since 800 < 1000
                    assert result.total_passes == 1
                    assert result.final_tokens == 800
                    assert len(result.passes) == 1

    @pytest.mark.asyncio
    async def test_max_passes_exhausted(self):
        """Test when max passes is reached without hitting target."""
        mock_llm = MagicMock()

        # Simulate slow reduction that doesn't reach target
        token_counts = [10000, 8000, 6500, 5200]
        count_idx = [0]

        def mock_count_tokens(*args, **kwargs):
            result = token_counts[count_idx[0]]
            count_idx[0] = min(count_idx[0] + 1, len(token_counts) - 1)
            return result

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = mock_count_tokens

            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                mock_max_context.return_value = 128000

                with patch(
                    "src.shared.llm.summarization.progressive.perform_summary_pass"
                ) as mock_perform:

                    async def mock_pass(text, llm, pass_number, target_tokens):
                        return SummaryPass(
                            pass_number=pass_number,
                            input_tokens=token_counts[pass_number - 1],
                            output_tokens=token_counts[pass_number],
                            reduction_ratio=0.2,
                            summary=f"Pass {pass_number} summary",
                            key_points_retained=[],
                            topics_covered=[],
                        )

                    mock_perform.side_effect = mock_pass

                    result = await progressive_summarize(
                        text="Text with slow reduction",
                        llm=mock_llm,
                        target_tokens=1000,
                        max_passes=3,
                    )

                    # Should complete all 3 passes
                    assert result.total_passes == 3
                    # Should have warning that target wasn't reached
                    assert any("exceeds target" in w for w in result.warnings)
                    assert result.final_tokens == 5200

    @pytest.mark.asyncio
    async def test_chunking_with_single_chunk(self):
        """Test chunking when document splits into single chunk."""
        mock_llm = MagicMock()

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            # Original, in summarize_with_chunking, combined, after chunking
            # loop check, final
            mock_count.side_effect = [70000, 70000, 28000, 28000, 28000, 28000]

            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                mock_max_context.return_value = 128000  # Threshold: 64k

                with patch(
                    "src.shared.llm.summarization.progressive.chunk_text_by_tokens"
                ) as mock_chunk:
                    # Single chunk
                    mock_chunk.return_value = ["single chunk"]

                    with patch(
                        "src.shared.llm.summarization.progressive.summarize_chunk"
                    ) as mock_summarize_chunk:

                        async def mock_chunk_summary(*args, **kwargs):
                            return ChunkSummary(
                                chunk_number=1,
                                input_tokens=70000,
                                output_tokens=28000,
                                summary="Single chunk summary",
                                key_points=["Point 1"],
                            )

                        mock_summarize_chunk.side_effect = mock_chunk_summary

                        result = await progressive_summarize(
                            text="Large text",
                            llm=mock_llm,
                            target_tokens=30000,
                        )

                        assert result.was_chunked is True
                        assert result.num_chunks == 1
                        assert result.total_passes == 0  # Within target after chunking


@pytest.mark.unit
class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_large_document_with_chunking_and_passes(self):
        """Test large document requiring both chunking and progressive passes."""
        mock_llm = MagicMock()

        # Large doc (150k) -> chunks (50k) -> pass1 (30k) -> pass2 (12k)
        # count_tokens sequence (summarize_with_chunking is mocked,
        # so its internal calls don't count):
        # 1. Line 359: original check (150k)
        # 2. Line 421: after chunking logging (50k)
        # 3. Line 435: loop iteration 1 start (50k)
        # 4. Line 435: loop iteration 2 start (30k)
        # 5. Line 435: loop iteration 3 start (12k - should exit)
        # 6. Line 475: final check (12k)
        token_counts = [150000, 50000, 50000, 30000, 12000, 12000]
        count_idx = [0]

        def mock_count_tokens(*args, **kwargs):
            result = token_counts[count_idx[0]]
            count_idx[0] = min(count_idx[0] + 1, len(token_counts) - 1)
            return result

        with patch(
            "src.shared.llm.summarization.progressive.count_tokens"
        ) as mock_count:
            mock_count.side_effect = mock_count_tokens

            with patch(
                "src.shared.llm.summarization.progressive.get_max_context_tokens"
            ) as mock_max_context:
                mock_max_context.return_value = 128000

                with patch(
                    "src.shared.llm.summarization.progressive."
                    "summarize_with_chunking"
                ) as mock_chunk_summarize:

                    async def mock_chunking(*args, **kwargs):
                        return (
                            "Combined chunk summary (50k tokens)",
                            [
                                ChunkSummary(
                                    chunk_number=i,
                                    input_tokens=50000,
                                    output_tokens=16667,
                                    summary=f"Chunk {i} summary",
                                    key_points=[],
                                )
                                for i in range(1, 4)
                            ],
                            [],
                        )

                    mock_chunk_summarize.side_effect = mock_chunking

                    with patch(
                        "src.shared.llm.summarization.progressive."
                        "perform_summary_pass"
                    ) as mock_perform:

                        # Track pass invocations to return correct values
                        pass_invocations = [0]

                        async def mock_pass(text, llm, pass_number, target_tokens):
                            pass_invocations[0] += 1
                            # Return correct input/output based on invocation order
                            if pass_invocations[0] == 1:
                                return SummaryPass(
                                    pass_number=1,
                                    input_tokens=50000,
                                    output_tokens=30000,
                                    reduction_ratio=0.4,
                                    summary="Pass 1 summary",
                                    key_points_retained=[],
                                    topics_covered=[],
                                )

                            return SummaryPass(
                                pass_number=2,
                                input_tokens=30000,
                                output_tokens=12000,
                                reduction_ratio=0.6,
                                summary="Pass 2 summary",
                                key_points_retained=[],
                                topics_covered=[],
                            )

                        mock_perform.side_effect = mock_pass

                        result = await progressive_summarize(
                            text="Extremely large document",
                            llm=mock_llm,
                            target_tokens=15000,
                        )

                        # Should use chunking AND progressive passes
                        assert result.was_chunked is True
                        assert result.num_chunks == 3
                        assert result.total_passes == 2
                        assert result.final_tokens == 12000

    @pytest.mark.asyncio
    async def test_conservative_strategy_preserves_more(self):
        """Test that conservative strategy uses gentler reduction."""
        targets = calculate_reduction_targets(
            original_tokens=10000,
            target_tokens=1000,
            max_passes=3,
            strategy=SummarizationStrategy.CONSERVATIVE,
        )

        # Conservative should keep more tokens at each pass
        assert targets[0] == 7000  # 70% retention
        assert targets[1] == 3500  # 50% retention
        assert targets[2] == 1225  # 35% retention

    @pytest.mark.asyncio
    async def test_aggressive_strategy_reduces_faster(self):
        """Test that aggressive strategy uses faster reduction."""
        targets = calculate_reduction_targets(
            original_tokens=10000,
            target_tokens=1000,
            max_passes=3,
            strategy=SummarizationStrategy.AGGRESSIVE,
        )

        # Aggressive should reduce more aggressively
        assert targets[0] == 5000  # 50% retention
        assert targets[1] == 1500  # 30% retention
        assert targets[2] == 1000  # Target reached
