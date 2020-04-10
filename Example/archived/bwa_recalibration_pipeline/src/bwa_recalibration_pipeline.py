#!/usr/bin/env python
#
# Copyright (C) 2013 DNAnexus, Inc.
#   This file is part of dnanexus-example-applets.
#   You may use this file under the terms of the Apache License, Version 2.0;
#   see the License.md file for more information.


# bwa_recalibration_pipeline 0.0.1
# Generated by dx-app-wizard.
#
# Parallelized execution pattern: Your app will generate multiple jobs
# to perform some computation in parallel, followed by a final
# "postprocess" stage that will perform any additional computations as
# necessary.
#
# See http://wiki.dnanexus.com/Developer-Tutorials/Intro-to-Building-Apps
# for instructions on how to modify this file.
#
# DNAnexus Python Bindings (dxpy) documentation:
#   http://autodoc.dnanexus.com/bindings/python/current/

import os
import dxpy

import re
import subprocess

@dxpy.entry_point('main')
def main(reads_per_chunk, left_reads, right_reads, reference, dbsnp, known_indels, indexed_reference, genome_splits=10, aln_params="", samse_sampe_params="-r '@RG\tID:1\tPL:ILLUMINA\tPU:None\tLB:1\tSM:1'", mark_duplicates_params="ASSUME_SORTED=true VALIDATION_STRINGENCY=LENIENT", count_covariates_params="", target_creator_params="", indel_realigner_params="", table_recalibrator_params=""):

    parallel_bwa_job = applet("parallel_bwa").run({"fastq_gz_left_reads": left_reads, "fastq_gz_right_reads": right_reads, "indexed_reference": indexed_reference, "reads_per_chunk": reads_per_chunk, "aln_params": aln_params, "sampe_params": samse_sampe_params})

    split_interchromosomal_job = applet("split_bam_interchromosomal_pairs").run({"BAM": {"job": parallel_bwa_job.get_id(), "field": "BAM"} })
    best_practices_jobs = []

    #Run deduplication and best practices on the mappings of interchromosomally mapped read pairs
    best_practices_jobs.append(run_best_practices_jobs({"job": split_interchromosomal_job.get_id(), "field": "interchromosomal_BAM"}, mark_duplicates_params, reference, dbsnp, known_indels, count_covariates_params, target_creator_params, indel_realigner_params, table_recalibrator_params))

    #Run deduplication and best practices on the mappings of intrachromosomally mapped read pairs
    for x in split_genome(dxpy.DXFile(reference), genome_splits):
        view_options = "-h -b " + " ".join(x)
        gatk_regions = " -L " + " -L ".join(x)
        samtools_view_job = applet("samtools_view").run({"BAM": {"job":split_interchromosomal_job.get_id(), "field":"intrachromosomal_BAM"}, "params": view_options})
        best_practices_jobs.append(run_best_practices_jobs({"job": samtools_view_job.get_id(), "field": "BAM"}, mark_duplicates_params, reference, dbsnp, known_indels, count_covariates_params, target_creator_params, indel_realigner_params, table_recalibrator_params))

    final_merge_input = {"BAMs" : []}
    for x in best_practices_jobs:
        final_merge_input["BAMs"].append({"job": x.get_id(), "field":"BAM"})
    final_merge_job = applet("picard_merge_sam_files").run(final_merge_input)

    output = {"recalibrated_bam": {"job": final_merge_job.get_id(), "field": "BAM"}, "raw_bam":  {"job": parallel_bwa_job.get_id(), "field": "BAM"} }

    return output

def run_best_practices_jobs(BAM, mark_duplicates_params, reference, dbsnp, known_indels, count_covariates_params, target_creator_params, indel_realigner_params, table_recalibrator_params):
    mark_duplicates_job = applet("picard_mark_duplicates").run({
                "BAM": BAM,
                "params": mark_duplicates_params})

    return applet("gatk_realign_and_recalibrate_applet").run({
                    "BAM": {"job": mark_duplicates_job.get_id(), "field": "BAM"},
                    "reference": reference,
                    "dbsnp": dbsnp,
                    "known_indels": known_indels,
                    "count_covariates_params": count_covariates_params,
                    "target_creator_params": target_creator_params,
                    "indel_realigner_params": indel_realigner_params,
                    "table_recalibrator_params": table_recalibrator_params})


def split_genome(reference, splits):

    # Extract the reference file
    dxpy.download_dxfile(reference.get_id(), "ref.fa.gz")
    subprocess.check_call("gzip -d ref.fa.gz", shell=True)

    chromosomes = []
    for x in range(splits):
        chromosomes.append([])
    i = 0
    for line in open("ref.fa", 'r'):
        if len(re.findall(">([^\n]*)\n", line)) > 0:
            chromosomes[i%splits].append(re.findall(">([^\n]*)\n", line)[0])
            i += 1
    return chromosomes

def applet(name):
    return find_in_project(name=name, classname="applet", return_handler=True)

def find_in_project(**kwargs):
    kwargs["project"] = os.environ["DX_PROJECT_CONTEXT_ID"]
    return dxpy.find_one_data_object(**kwargs)

dxpy.run()